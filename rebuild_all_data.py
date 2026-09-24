import os
import sys
import json
import psycopg2
import time
from datetime import datetime

DB_HOST = os.environ.get('DB_HOST', 'org-db.cgtvjodbp1rf.ap-south-1.rds.amazonaws.com')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_USER = os.environ.get('DB_USER', 'mayur_de')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'blyer9263@kk')
DB_NAME = os.environ.get('DB_NAME', 'votexdb')

STATE_NAMES = {
    'AN': 'Andaman & Nicobar Islands', 'AP': 'Andhra Pradesh', 'AR': 'Arunachal Pradesh', 'AS': 'Assam',
    'BR': 'Bihar', 'CH': 'Chandigarh', 'CG': 'Chhattisgarh', 'DD': 'Daman & Diu', 'DL': 'Delhi',
    'DN': 'Dadra & Nagar Haveli', 'GA': 'Goa', 'GJ': 'Gujarat', 'HP': 'Himachal Pradesh', 'HR': 'Haryana',
    'JH': 'Jharkhand', 'JK': 'Jammu & Kashmir', 'KA': 'Karnataka', 'KL': 'Kerala', 'LA': 'Ladakh',
    'LD': 'Lakshadweep', 'MH': 'Maharashtra', 'ML': 'Meghalaya', 'MN': 'Manipur', 'MP': 'Madhya Pradesh',
    'MZ': 'Mizoram', 'NL': 'Nagaland', 'OR': 'Odisha', 'PB': 'Punjab', 'PY': 'Puducherry', 'RJ': 'Rajasthan',
    'SK': 'Sikkim', 'TN': 'Tamil Nadu', 'TR': 'Tripura', 'TS': 'Telangana', 'UK': 'Uttarakhand',
    'UP': 'Uttar Pradesh', 'WB': 'West Bengal'
}

STATE_AC_COUNTS = {
    'AN': 1, 'AP': 175, 'AR': 60, 'AS': 126, 'BR': 243, 'CH': 1, 'CG': 90, 'DD': 1, 'DL': 70,
    'DN': 1, 'GA': 40, 'GJ': 182, 'HP': 68, 'HR': 90, 'JH': 81, 'JK': 90, 'KA': 224, 'KL': 140,
    'LA': 1, 'LD': 1, 'MH': 288, 'ML': 60, 'MN': 60, 'MP': 230, 'MZ': 40, 'NL': 60, 'OR': 147,
    'PB': 117, 'PY': 30, 'RJ': 200, 'SK': 32, 'TN': 234, 'TR': 60, 'TS': 119, 'UK': 70,
    'UP': 403, 'WB': 294
}

def get_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, dbname=DB_NAME)

def build_all_data():
    conn = get_conn()
    cur = conn.cursor()
    
    # Overall stats for weighted national average
    global_expected = 0
    global_retro_av = 0
    global_form20_av = 0
    
    # 1. Expected ACs
    cur.execute("""
        SELECT state_abb, el_type, el_year, COUNT(DISTINCT ac_no) 
        FROM ac_election_mapping 
        WHERE el_type NOT LIKE '%BP%'
        GROUP BY state_abb, el_type, el_year;
    """)
    expected_rows = cur.fetchall()
    expected = {}
    for st, ty, yr, c in expected_rows:
        st = st.strip()
        ty = ty.strip()
        expected.setdefault(st, {}).setdefault(ty, {})[int(yr)] = c

    # 2. Retro Available ACs
    cur.execute("""
        SELECT er.state_abb, e.el_type, e.el_year, COUNT(DISTINCT er.ac_no) 
        FROM election_result er
        JOIN election e ON e.el_id = er.el_id
        WHERE e.el_type NOT LIKE '%BP%'
        GROUP BY er.state_abb, e.el_type, e.el_year;
    """)
    retro_rows = cur.fetchall()
    retro = {}
    for st, ty, yr, c in retro_rows:
        st = st.strip()
        ty = ty.strip()
        retro.setdefault(st, {}).setdefault(ty, {})[int(yr)] = c

    # 3. Form 20 Available ACs
    cur.execute("""
        SELECT state_abb, el_type, el_year, COUNT(DISTINCT ac_no) 
        FROM form20_summary_view 
        WHERE el_type NOT LIKE '%BP%'
        GROUP BY state_abb, el_type, el_year;
    """)
    form20_rows = cur.fetchall()
    form20 = {}
    for st, ty, yr, c in form20_rows:
        st = st.strip()
        ty = ty.strip()
        form20.setdefault(st, {}).setdefault(ty, {})[int(yr)] = c

    # 4. Caste Available ACs
    cur.execute("SELECT state_abb, COUNT(DISTINCT ac_no) FROM caste_details GROUP BY state_abb;")
    caste_rows = cur.fetchall()
    caste = {str(r[0]).strip(): r[1] for r in caste_rows}

    # 5. Booth Available ACs
    cur.execute("SELECT state_abb, COUNT(DISTINCT ac_no) FROM ac_details GROUP BY state_abb;")
    booth_rows = cur.fetchall()
    booth = {str(r[0]).strip(): r[1] for r in booth_rows}
    
    # Optional other sources for Country Glance Map (dummy or fetched if needed)
    # We will just fetch the basics for the main dashboards here.
    # If the other metrics (muslim, joshua, etc) are needed for country glance,
    # we copy their logic from generate_glance_data.py
    print("Fetching third party data...")
    cur.execute("SELECT state_abb, COUNT(DISTINCT district_name) FROM muslim_census GROUP BY state_abb;")
    muslim = {str(r[0]).strip(): r[1] for r in cur.fetchall()}
    cur.execute("SELECT state_abb, COUNT(DISTINCT district_name) FROM joshua_population GROUP BY state_abb;")
    joshua = {str(r[0]).strip(): r[1] for r in cur.fetchall()}
    cur.execute("SELECT state_abb, COUNT(DISTINCT district_name) FROM school_locator WHERE district_name IS NOT NULL GROUP BY state_abb;")
    kys = {str(r[0]).strip(): r[1] for r in cur.fetchall()}
    cur.execute("SELECT ld.state_abb, COUNT(DISTINCT ep.lgd_code) FROM ejalshakti_portal ep JOIN lgd_directory ld ON ld.lgd_code = ep.lgd_code GROUP BY ld.state_abb;")
    ejal = {str(r[0]).strip(): r[1] for r in cur.fetchall()}
    cur.execute("SELECT state_abb, COUNT(DISTINCT lgd_code) FROM secc_abstract GROUP BY state_abb;")
    secc = {str(r[0]).strip(): r[1] for r in cur.fetchall()}
    cur.execute("SELECT state_abb, COUNT(DISTINCT district_code) FROM lgd_directory GROUP BY state_abb;")
    lgd_districts = {str(r[0]).strip(): r[1] for r in cur.fetchall()}

    cur.close()
    conn.close()

    print("Building State and Country Data structures...")
    
    # Load existing state_glance to preserve layout and any non-computed fields if necessary
    state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'data', 'state_glance_cache.json')
    if os.path.exists(state_path):
        with open(state_path, 'r') as f:
            state_glance = json.load(f)
    else:
        state_glance = {}

    glance_matrix = []
    
    for abb, name in STATE_NAMES.items():
        total_expected_acs = 0
        total_retro_av = 0
        total_form20_av = 0
        
        matrix_ae = []
        matrix_ge = []
        
        # Calculate Retro and Form20
        st_exp = expected.get(abb, {})
        for ty in ['AE', 'GE']:
            for yr, exp_c in st_exp.get(ty, {}).items():
                if exp_c <= 0: continue
                total_expected_acs += exp_c
                
                # Fetch Retro and Form20 ACs (cap at expected)
                av_r = min(retro.get(abb, {}).get(ty, {}).get(yr, 0), exp_c)
                av_f = min(form20.get(abb, {}).get(ty, {}).get(yr, 0), exp_c)
                
                total_retro_av += av_r
                total_form20_av += av_f
                
                # Build Matrix Item
                pct = round((av_r / exp_c * 100), 2)
                item = {
                    "year": yr,
                    "availability": pct,
                    "missing": exp_c - av_r,
                    "missing_acs": []
                }
                if ty == 'AE':
                    matrix_ae.append(item)
                else:
                    matrix_ge.append(item)
                    
        matrix_ae.sort(key=lambda x: int(x['year']), reverse=True)
        matrix_ge.sort(key=lambda x: int(x['year']), reverse=True)
        
        retro_pct = round((total_retro_av / total_expected_acs * 100), 2) if total_expected_acs > 0 else 0.0
        form20_pct = round((total_form20_av / total_expected_acs * 100), 2) if total_expected_acs > 0 else 0.0
        
        global_retro_av += total_retro_av
        global_form20_av += total_form20_av
        global_expected += total_expected_acs
        
        # Caste and Booth (based on STATE_AC_COUNTS)
        base_ac = STATE_AC_COUNTS.get(abb, 1)
        caste_pct = round((min(caste.get(abb, 0), base_ac) / base_ac * 100), 2)
        booth_pct = round((min(booth.get(abb, 0), base_ac) / base_ac * 100), 2)
        
        # Country Glance Matrix Row
        glance_matrix.append({
            'state_abb': abb,
            'state_name': name,
            'retro': retro_pct,
            'form20': form20_pct,
            'caste': caste_pct,
            'booth': booth_pct,
            'muslim': round(min((muslim.get(abb, 0) / max(lgd_districts.get(abb, 1), 1) * 100), 100), 2),
            'joshua': round(min((joshua.get(abb, 0) / max(lgd_districts.get(abb, 1), 1) * 100), 100), 2),
            'kys': round(min((kys.get(abb, 0) / max(lgd_districts.get(abb, 1), 1) * 100), 100), 2),
            'lgd': 100.0 if lgd_districts.get(abb, 0) > 0 else 0.0,
            'ejal': round(min((ejal.get(abb, 0) / max(lgd_districts.get(abb, 1), 1) * 100), 100), 2),
            'secc': round(min((secc.get(abb, 0) / max(lgd_districts.get(abb, 1), 1) * 100), 100), 2),
            'nrega': 100.0,
            'indiastat': 100.0 if abb in ['AP', 'BR', 'CG', 'GA', 'GJ', 'HR', 'HP', 'JH', 'JK', 'KA', 'KL', 'MP', 'MH', 'OR', 'PB', 'RJ', 'TN', 'UK', 'UP', 'WB'] else 0.0,
            'lens': 100.0 if retro_pct > 0 else 0.0
        })
        
        # State Report Sync
        if abb not in state_glance:
            state_glance[abb] = {}
            
        if 'hero' not in state_glance[abb]: state_glance[abb]['hero'] = {}
        state_glance[abb]['hero']['retro_availability_pct'] = retro_pct
        state_glance[abb]['hero']['total_acs'] = base_ac
        
        if 'form20' not in state_glance[abb]: state_glance[abb]['form20'] = {}
        state_glance[abb]['form20']['availability_pct'] = form20_pct
        
        if 'retro' not in state_glance[abb]: state_glance[abb]['retro'] = {}
        state_glance[abb]['retro']['matrix_ae'] = matrix_ae
        state_glance[abb]['retro']['matrix_ge'] = matrix_ge
        
        if 'caste' not in state_glance[abb]: state_glance[abb]['caste'] = {}
        state_glance[abb]['caste']['availability_pct'] = caste_pct
        
        if 'booth' not in state_glance[abb]: state_glance[abb]['booth'] = {}
        state_glance[abb]['booth']['availability_pct'] = booth_pct

    # Write state_glance_cache.json
    with open(state_path, 'w') as f:
        json.dump(state_glance, f, indent=2)
        
    glance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'data', 'glance_cache.json')
    global_retro_pct = round((global_retro_av / global_expected * 100), 2) if global_expected > 0 else 0.0
    global_form20_pct = round((global_form20_av / global_expected * 100), 2) if global_expected > 0 else 0.0

    # Apply Frontend Mappings: CH -> CG, CG -> CT
    frontend_matrix = []
    for item in glance_matrix:
        new_item = item.copy()
        if new_item['state_abb'] == 'CH':
            new_item['state_abb'] = 'CG'
        elif new_item['state_abb'] == 'CG':
            new_item['state_abb'] = 'CT'
        frontend_matrix.append(new_item)

    with open(glance_path, 'w') as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "national_avg": {
                "retro": global_retro_pct,
                "form20": global_form20_pct,
                "caste": round(sum(r['caste'] for r in glance_matrix) / len(glance_matrix), 2),
                "booth": round(sum(r['booth'] for r in glance_matrix) / len(glance_matrix), 2),
            },
            "matrix": frontend_matrix
        }, f, indent=2)
        
    # Push State data to Redis!
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        for abb, data in state_glance.items():
            redis_abb = abb
            if abb == 'CH':
                redis_abb = 'CG'
            elif abb == 'CG':
                redis_abb = 'CT'
            r.set(f"state_glance:{redis_abb}", json.dumps(data))
    except Exception as e:
        print(f"Error syncing to redis: {e}")
        
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        with open(glance_path, 'r') as f:
            country_data = json.load(f)
        r.set('cache:country_glance_data:data', json.dumps(country_data))
    except Exception as e:
        print(f"Error syncing country data to redis: {e}")
        
    print("ALL CACHES REBUILT AND UNIFIED.")

if __name__ == '__main__':
    build_all_data()
