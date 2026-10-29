"""
Computes dynamic AC-wise, Election-wise, and State-wide Vote Mismatch
between Form 20 extracted data and ECI Retro data from votexdb.
Formula: (|Form20 Votes - Retro Votes| / Retro Votes) * 100
"""

import os
import json
import time
import psycopg2
import redis
import threading
from concurrent.futures import ThreadPoolExecutor

CACHE_LOCK = threading.Lock()

def get_db_connection():
    return psycopg2.connect(
        host="org-db.cgtvjodbp1rf.ap-south-1.rds.amazonaws.com",
        port=5432,
        user="mayur_de",
        password="blyer9263@kk",
        dbname="votexdb",
        connect_timeout=20,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5
    )

def sync_to_redis(state_abb, state_data):
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, socket_connect_timeout=2)
        r.set(f"state_glance:{state_abb}", json.dumps(state_data))
    except Exception:
        pass

def compute_mismatch_for_state(state_abb):
    t_start = time.time()
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 1. Fetch Retro votes per AC
        cur.execute("""
            SELECT e.el_year, e.el_type, r.ac_no, SUM(r.el_vote_count) as retro_votes
            FROM election e
            JOIN election_result r ON e.el_id = r.el_id
            WHERE r.state_abb = %s
            GROUP BY e.el_year, e.el_type, r.ac_no;
        """, (state_abb,))
        retro_data = {}
        for yr, ty, ac_no, votes in cur.fetchall():
            key = (str(yr), ty)
            if key not in retro_data:
                retro_data[key] = {}
            retro_data[key][ac_no] = float(votes or 0)

        # 2. Fetch Form20 votes per AC
        cur.execute("""
            SELECT el_year, el_type, ac_no, SUM(total_votes) as f20_votes
            FROM form20_summary_view
            WHERE state_abb = %s
            GROUP BY el_year, el_type, ac_no;
        """, (state_abb,))
        f20_data = {}
        for yr, ty, ac_no, votes in cur.fetchall():
            key = (str(yr), ty)
            if key not in f20_data:
                f20_data[key] = {}
            f20_data[key][ac_no] = float(votes or 0)

        cur.close()
        conn.close()
        conn = None

        # 3. Calculate AC-wise, Election-wise, and State-wide Mismatch
        election_mismatches = {}
        tot_abs_diff = 0.0
        tot_net_diff = 0.0
        tot_retro_votes = 0.0

        all_keys = set(retro_data.keys()).union(set(f20_data.keys()))

        for key in all_keys:
            yr, ty = key
            r_acs = retro_data.get(key, {})
            f_acs = f20_data.get(key, {})

            all_ac_nos = set(r_acs.keys()).union(set(f_acs.keys()))
            if not all_ac_nos:
                continue

            el_abs_diff = 0.0
            el_net_diff = 0.0
            el_retro_votes = 0.0

            for ac_no in all_ac_nos:
                r_val = r_acs.get(ac_no, 0.0)
                f_val = f_acs.get(ac_no, 0.0)

                diff = abs(f_val - r_val)
                signed_diff = f_val - r_val
                el_abs_diff += diff
                el_net_diff += signed_diff
                el_retro_votes += r_val

                # Include regular elections in overall state calculation if Form 20 exists for it
                if 'BP' not in ty and f_val > 0:
                    tot_abs_diff += diff
                    tot_net_diff += signed_diff
                    tot_retro_votes += r_val

            # Election mismatch: aggregate weighted difference across ACs
            if el_retro_votes > 0 and len(f_acs) > 0:
                el_mismatch_pct = round((el_abs_diff / el_retro_votes * 100.0), 2)
                el_net_pct = round((el_net_diff / el_retro_votes * 100.0), 2)
            else:
                el_mismatch_pct = 0.0
                el_net_pct = 0.0

            election_mismatches[key] = {
                'mismatch_pct': el_mismatch_pct,
                'net_diff': round(el_net_diff),
                'net_diff_pct': el_net_pct
            }

        # Overall State Deviation across regular elections
        if tot_retro_votes > 0:
            overall_state_pct = round((tot_abs_diff / tot_retro_votes * 100.0), 2)
            overall_net_diff = round(tot_net_diff)
            overall_net_pct = round((tot_net_diff / tot_retro_votes * 100.0), 2)
            dev_cat = "Low" if overall_state_pct < 2.5 else ("Medium" if overall_state_pct <= 5.0 else "High")
        else:
            overall_state_pct = 0.0
            overall_net_diff = 0
            overall_net_pct = 0.0
            dev_cat = "Low"

        # Apply to cache
        update_cache_file(state_abb, election_mismatches, overall_state_pct, overall_net_diff, overall_net_pct, dev_cat)
        duration = time.time() - t_start
        print(f"[{time.strftime('%X')}] [OK] {state_abb:4s}: Overall={overall_state_pct}% ({dev_cat}, Net={overall_net_diff:+,d} votes), Elections={len(election_mismatches)} in {duration:.2f}s")
        return state_abb, overall_state_pct, dev_cat

    except Exception as e:
        print(f"[{time.strftime('%X')}] [ERROR] {state_abb}: {e}")
        if conn:
            try:
                conn.close()
            except:
                pass
        return state_abb, None, None

def update_cache_file(state_abb, election_mismatches, overall_state_pct, overall_net_diff, overall_net_pct, dev_cat):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_path = os.path.join(base_dir, 'static', 'data', 'state_glance_cache.json')

    if not os.path.exists(cache_path):
        return

    with CACHE_LOCK:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache = json.load(f)

        if state_abb not in cache:
            return

        st_data = cache[state_abb]
        if 'form20' not in st_data or not isinstance(st_data['form20'], dict):
            st_data['form20'] = {}

        f20 = st_data['form20']
        f20['vote_mismatch_pct'] = overall_state_pct
        f20['net_bias_votes'] = overall_net_diff
        f20['net_bias_pct'] = overall_net_pct
        f20['deviation_cat'] = dev_cat

        def apply_matrix_mismatch(matrix, el_type):
            for item in matrix:
                yr = str(item.get('year'))
                k = (yr, el_type)
                if k in election_mismatches:
                    m_data = election_mismatches[k]
                    item['vote_mismatch'] = m_data['mismatch_pct']
                    item['net_diff'] = m_data['net_diff']
                    item['net_diff_pct'] = m_data['net_diff_pct']
                elif item.get('vote_mismatch') == 2.41:
                    item['vote_mismatch'] = 0.0
                    item['net_diff'] = 0
                    item['net_diff_pct'] = 0.0

        apply_matrix_mismatch(f20.get('matrix_ae', []), 'AE')
        apply_matrix_mismatch(f20.get('matrix_ge', []), 'GE')
        apply_matrix_mismatch(f20.get('matrix_ae_bp', []), 'AE-BP')
        apply_matrix_mismatch(f20.get('matrix_ge_bp', []), 'GE-BP')

        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2)

        sync_to_redis(state_abb, st_data)

def process_all_states():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_path = os.path.join(base_dir, 'static', 'data', 'state_glance_cache.json')
    with open(cache_path, 'r', encoding='utf-8') as f:
        cache = json.load(f)

    states = list(cache.keys())
    print(f"[{time.strftime('%X')}] Starting Vote Mismatch calculation for {len(states)} states using 6 parallel threads...")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(compute_mismatch_for_state, states))

    print(f"[{time.strftime('%X')}] Finished processing all {len(states)} states in {time.time()-t0:.2f}s!")

if __name__ == '__main__':
    import sys
    target = sys.argv[1].upper() if len(sys.argv) > 1 else 'ALL'
    if target == 'ALL':
        process_all_states()
    else:
        compute_mismatch_for_state(target)
