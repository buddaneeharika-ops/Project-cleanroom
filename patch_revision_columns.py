import os
import json
import time
import pg8000.dbapi as dbapi
from dotenv import load_dotenv

load_dotenv()

CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'data', 'state_glance_cache.json')

def patch_cache_with_revisions():
    print("=== Patching state_glance_cache.json with 3-Column Revision Data (Pre-SIR, SIR, Post-SIR) ===")
    t0 = time.time()
    
    if not os.path.exists(CACHE_PATH):
        print(f"[ERROR] Cache file not found: {CACHE_PATH}")
        return False
        
    with open(CACHE_PATH, 'r', encoding='utf-8') as f:
        cache_data = json.load(f)
        
    print(f"Loaded existing cache with {len(cache_data)} states.")

    # Connect to RDS votexdb
    conn = dbapi.connect(
        host=os.getenv('DB_HOST', 'org-db.cgtvjodbp1rf.ap-south-1.rds.amazonaws.com'),
        port=5432,
        database='votexdb',
        user='neeharika_ka_de',
        password='dvhbdaybndkfkj1274nd'
    )
    cur = conn.cursor()

    # 1. State-level revision aggregation
    print("[1/2] Querying State-level revision counts...")
    cur.execute('''
        SELECT 
            b.state_abb,
            COUNT(CASE WHEN NOT (lower(p.type_of_revision) LIKE '%final%' 
                              OR lower(p.type_of_revision) LIKE '%continuous%' 
                              OR lower(p.type_of_revision) LIKE '%supplement%' 
                              OR lower(p.type_of_revision) LIKE '%post%')
                        AND (lower(p.type_of_revision) LIKE '%draft%' 
                          OR lower(p.type_of_revision) LIKE '%integrated%' 
                          OR lower(p.type_of_revision) LIKE '%pre%') 
                       THEN 1 END) as pre_sir,
            COUNT(CASE WHEN NOT (lower(p.type_of_revision) LIKE '%final%' 
                              OR lower(p.type_of_revision) LIKE '%continuous%' 
                              OR lower(p.type_of_revision) LIKE '%supplement%' 
                              OR lower(p.type_of_revision) LIKE '%post%')
                        AND NOT (lower(p.type_of_revision) LIKE '%draft%' 
                              OR lower(p.type_of_revision) LIKE '%integrated%' 
                              OR lower(p.type_of_revision) LIKE '%pre%')
                        AND (lower(p.type_of_revision) LIKE '%intensive%' 
                          OR lower(p.type_of_revision) LIKE '%summary%' 
                          OR lower(p.type_of_revision) LIKE '%sir%' 
                          OR lower(p.type_of_revision) LIKE '%ssr%' 
                          OR lower(p.type_of_revision) LIKE '%revision%' 
                          OR lower(p.type_of_revision) LIKE '%punrikshan%' 
                          OR lower(p.type_of_revision) LIKE '%punarikshan%'
                          OR lower(p.type_of_revision) LIKE '%voter list%'
                          OR lower(p.type_of_revision) LIKE '%electoral roll%')
                       THEN 1 END) as sir,
            COUNT(CASE WHEN lower(p.type_of_revision) LIKE '%final%' 
                         OR lower(p.type_of_revision) LIKE '%continuous%' 
                         OR lower(p.type_of_revision) LIKE '%supplement%' 
                         OR lower(p.type_of_revision) LIKE '%post%' 
                       THEN 1 END) as post_sir,
            COUNT(*) as total_booths,
            MAX(p.type_of_revision) as sample_revision
        FROM booth_metadata b
        JOIN booth_metadata_polling_station p ON b.el_booth_id = p.el_booth_id
        GROUP BY b.state_abb
        ORDER BY b.state_abb;
    ''')
    state_rows = cur.fetchall()
    
    state_revisions = {}
    for r in state_rows:
        s_abb = 'CH' if r[0] == 'CG' else r[0]
        pre, sir, post, tot, s_rev = r[1], r[2], r[3], r[4], r[5]
        primary = 'Post-SIR' if post >= max(sir, pre) and post > 0 else ('Pre-SIR' if pre >= max(sir, post) and pre > 0 else 'SIR')
        state_revisions[s_abb] = {
            'pre_sir': pre,
            'sir': sir,
            'post_sir': post,
            'total': tot,
            'primary_stage': primary,
            'sample_revision': s_rev
        }
    print(f"State aggregation done ({len(state_revisions)} states with booth revisions).")

    # 2. AC-level revision aggregation
    print("[2/2] Querying AC-level revision counts...")
    cur.execute('''
        SELECT 
            b.state_abb,
            b.ac_no,
            COUNT(CASE WHEN NOT (lower(p.type_of_revision) LIKE '%final%' 
                              OR lower(p.type_of_revision) LIKE '%continuous%' 
                              OR lower(p.type_of_revision) LIKE '%supplement%' 
                              OR lower(p.type_of_revision) LIKE '%post%')
                        AND (lower(p.type_of_revision) LIKE '%draft%' 
                          OR lower(p.type_of_revision) LIKE '%integrated%' 
                          OR lower(p.type_of_revision) LIKE '%pre%') 
                       THEN 1 END) as pre_sir,
            COUNT(CASE WHEN NOT (lower(p.type_of_revision) LIKE '%final%' 
                              OR lower(p.type_of_revision) LIKE '%continuous%' 
                              OR lower(p.type_of_revision) LIKE '%supplement%' 
                              OR lower(p.type_of_revision) LIKE '%post%')
                        AND NOT (lower(p.type_of_revision) LIKE '%draft%' 
                              OR lower(p.type_of_revision) LIKE '%integrated%' 
                              OR lower(p.type_of_revision) LIKE '%pre%')
                        AND (lower(p.type_of_revision) LIKE '%intensive%' 
                          OR lower(p.type_of_revision) LIKE '%summary%' 
                          OR lower(p.type_of_revision) LIKE '%sir%' 
                          OR lower(p.type_of_revision) LIKE '%ssr%' 
                          OR lower(p.type_of_revision) LIKE '%revision%' 
                          OR lower(p.type_of_revision) LIKE '%punrikshan%' 
                          OR lower(p.type_of_revision) LIKE '%punarikshan%'
                          OR lower(p.type_of_revision) LIKE '%voter list%'
                          OR lower(p.type_of_revision) LIKE '%electoral roll%')
                       THEN 1 END) as sir,
            COUNT(CASE WHEN lower(p.type_of_revision) LIKE '%final%' 
                         OR lower(p.type_of_revision) LIKE '%continuous%' 
                         OR lower(p.type_of_revision) LIKE '%supplement%' 
                         OR lower(p.type_of_revision) LIKE '%post%' 
                       THEN 1 END) as post_sir,
            MAX(p.type_of_revision) as sample_revision,
            COUNT(*) as total_booths
        FROM booth_metadata b
        JOIN booth_metadata_polling_station p ON b.el_booth_id = p.el_booth_id
        GROUP BY b.state_abb, b.ac_no
        ORDER BY b.state_abb, b.ac_no;
    ''')
    ac_rows = cur.fetchall()
    
    ac_revisions = {}
    for r in ac_rows:
        s_abb = 'CH' if r[0] == 'CG' else r[0]
        ac_no = r[1]
        pre, sir, post, s_rev, tot = r[2], r[3], r[4], r[5], r[6]
        primary = 'Post-SIR' if post >= max(sir, pre) and post > 0 else ('Pre-SIR' if pre >= max(sir, post) and pre > 0 else 'SIR')
        ac_revisions[(s_abb, ac_no)] = {
            'pre_sir': pre,
            'sir': sir,
            'post_sir': post,
            'primary_stage': primary,
            'type_of_revision': s_rev,
            'total': tot
        }
    print(f"AC aggregation done ({len(ac_revisions)} ACs processed).")
    conn.close()

    # 3. Patching Cache Data
    print("Patching cache data in-memory...")
    for s_abb, s_data in cache_data.items():
        b_data = s_data.get('booth')
        if not b_data:
            continue
            
        s_rev_info = state_revisions.get(s_abb, {
            'pre_sir': 0,
            'sir': 0,
            'post_sir': 0,
            'total': b_data.get('total_booths', 0),
            'primary_stage': '—',
            'sample_revision': None
        })
        
        b_data['revision_breakdown'] = s_rev_info
        b_data['pre_sir_booths'] = s_rev_info['pre_sir']
        b_data['sir_booths'] = s_rev_info['sir']
        b_data['post_sir_booths'] = s_rev_info['post_sir']
        b_data['revision_stage'] = s_rev_info['primary_stage']
        
        # Patch AC-level booth_details list
        booth_details = b_data.get('booth_details', [])
        for ac_item in booth_details:
            ac_no = ac_item.get('ac_no')
            ac_rev_info = ac_revisions.get((s_abb, ac_no))
            if ac_rev_info:
                ac_item['pre_sir_booths'] = ac_rev_info['pre_sir']
                ac_item['sir_booths'] = ac_rev_info['sir']
                ac_item['post_sir_booths'] = ac_rev_info['post_sir']
                ac_item['revision_stage'] = ac_rev_info['primary_stage']
                ac_item['type_of_revision'] = ac_rev_info['type_of_revision']
            else:
                # Default to overall state stage if booth exists but no specific AC row
                ac_item['pre_sir_booths'] = 0
                ac_item['sir_booths'] = ac_item.get('extracted_booths', 0) if s_rev_info['primary_stage'] == 'SIR' else 0
                ac_item['post_sir_booths'] = ac_item.get('extracted_booths', 0) if s_rev_info['primary_stage'] == 'Post-SIR' else 0
                ac_item['revision_stage'] = s_rev_info['primary_stage']
                ac_item['type_of_revision'] = s_rev_info.get('sample_revision')

    # Save to file
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, indent=2)

    print(f"[SUCCESS] Successfully patched cache file at {CACHE_PATH} in {time.time()-t0:.2f}s!")
    return True

if __name__ == '__main__':
    patch_cache_with_revisions()
