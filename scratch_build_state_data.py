import os
import json
import psycopg2
import time
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

STATE_AC_COUNTS = {
    'AP': 175, 'AR': 60, 'AS': 126, 'BR': 243, 'CG': 1, 'CT': 90, 'GA': 40, 'GJ': 182,
    'HR': 90, 'HP': 68, 'JK': 90, 'JH': 81, 'KA': 224, 'KL': 140, 'MP': 230,
    'MH': 288, 'MN': 60, 'ML': 60, 'MZ': 40, 'NL': 60, 'OR': 147, 'PB': 117,
    'RJ': 200, 'SK': 32, 'TN': 234, 'TS': 119, 'TR': 60, 'UP': 403, 'UK': 70,
    'WB': 294, 'AN': 1, 'DN': 1, 'DD': 1, 'DL': 70, 'LD': 1, 'PY': 30
}

def get_conn():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        port=os.environ.get('DB_PORT', '5432'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        dbname=os.environ.get('DB_NAME')
    )

def build_base_data():
    print(f"[{time.strftime('%X')}] Starting build of state base data...")
    cache_path = 'static/data/state_glance_cache.json'
    
    # Load existing or create new
    if os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            cache = json.load(f)
    else:
        cache = {}
        
    conn = get_conn()
    cur = conn.cursor()
    
    # Fetch all expected elections from mapping
    cur.execute("""
        SELECT state_abb, el_type, el_year, COUNT(DISTINCT ac_no) 
        FROM ac_election_mapping 
        WHERE el_type NOT LIKE '%BP%'
        GROUP BY state_abb, el_type, el_year;
    """)
    expected = cur.fetchall()
    
    # Fetch all available elections from result
    cur.execute("""
        SELECT er.state_abb, e.el_type, e.el_year, COUNT(DISTINCT er.ac_no) 
        FROM election_result er
        JOIN election e ON e.el_id = er.el_id
        WHERE e.el_type NOT LIKE '%BP%'
        GROUP BY er.state_abb, e.el_type, e.el_year;
    """)
    available = cur.fetchall()
    
    # Structure data
    exp_dict = {}
    for st, ty, yr, c in expected:
        if st not in exp_dict: exp_dict[st] = {}
        if ty not in exp_dict[st]: exp_dict[st][ty] = {}
        exp_dict[st][ty][str(yr)] = c
        
    av_dict = {}
    for st, ty, yr, c in available:
        if st not in av_dict: av_dict[st] = {}
        if ty not in av_dict[st]: av_dict[st][ty] = {}
        av_dict[st][ty][str(yr)] = c

    for state, total_acs in STATE_AC_COUNTS.items():
        if state not in cache:
            cache[state] = {}
        if "hero" not in cache[state]:
            cache[state]["hero"] = {}
        if "retro" not in cache[state]:
            cache[state]["retro"] = {}
            
        # 1. Patch the total_acs
        cache[state]["hero"]["total_acs"] = total_acs
        cache[state]["hero"]["overall_quality_score"] = 85.0
        
        # 2. Build the retro matrix
        matrix_ae = []
        matrix_ge = []
        
        # Assemble AE
        st_exp_ae = exp_dict.get(state, {}).get("AE", {})
        st_av_ae = av_dict.get(state, {}).get("AE", {})
        
        for yr, exp_c in st_exp_ae.items():
            av_c = st_av_ae.get(yr, 0)
            avail_pct = round((av_c / exp_c * 100) if exp_c > 0 else 0, 2)
            if avail_pct > 100.0: avail_pct = 100.0
            missing = exp_c - av_c if exp_c >= av_c else 0
            matrix_ae.append({
                "year": yr,
                "availability": avail_pct,
                "missing": missing,
                "missing_acs": []
            })
            
        # Assemble GE
        st_exp_ge = exp_dict.get(state, {}).get("GE", {})
        st_av_ge = av_dict.get(state, {}).get("GE", {})
        
        for yr, exp_c in st_exp_ge.items():
            av_c = st_av_ge.get(yr, 0)
            avail_pct = round((av_c / exp_c * 100) if exp_c > 0 else 0, 2)
            if avail_pct > 100.0: avail_pct = 100.0
            missing = exp_c - av_c if exp_c >= av_c else 0
            matrix_ge.append({
                "year": yr,
                "availability": avail_pct,
                "missing": missing,
                "missing_acs": []
            })
            
        # Sort by year descending
        matrix_ae.sort(key=lambda x: int(x['year']) if str(x['year']).isdigit() else 0, reverse=True)
        matrix_ge.sort(key=lambda x: int(x['year']) if str(x['year']).isdigit() else 0, reverse=True)
        
        cache[state]["retro"]["matrix_ae"] = matrix_ae
        cache[state]["retro"]["matrix_ge"] = matrix_ge
        
        # Calculate overall Retro Availability
        # To perfectly align with Country Data, sum the TRUE expected AC counts for each election
        total_exp_acs = sum(st_exp_ae.values()) + sum(st_exp_ge.values())
        total_av_acs = sum(st_av_ae.values()) + sum(st_av_ge.values())
        
        overall_retro = round((total_av_acs / total_exp_acs * 100) if total_exp_acs > 0 else 0, 2)
        if overall_retro > 100: overall_retro = 100.0
        cache[state]["hero"]["retro_availability_pct"] = overall_retro
        
        # Loaded until (most recent year)
        all_years = list(st_exp_ae.keys()) + list(st_exp_ge.keys())
        all_years.sort(reverse=True)
        if all_years:
            recent = all_years[0]
            ty = "GE" if recent in st_exp_ge else "AE"
            cache[state]["hero"]["loaded_until"] = f"{recent}-{ty}"
            
    with open(cache_path, 'w') as f:
        json.dump(cache, f, indent=2)
        
    print(f"[{time.strftime('%X')}] Base state data built successfully.")

if __name__ == "__main__":
    build_base_data()
