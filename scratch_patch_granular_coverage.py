import psycopg2
import json

conn = psycopg2.connect(
    host='org-db.cgtvjodbp1rf.ap-south-1.rds.amazonaws.com',
    port='5432',
    user='mayur_de',
    password='blyer9263@kk',
    dbname='votexdb'
)
cur = conn.cursor()

def get_coverage(table_name, state_abb, col_name, join_col):
    # Total distinct items in LGD
    cur.execute(f"SELECT COUNT(DISTINCT {col_name}) FROM lgd_directory WHERE state_abb=%s AND {col_name} IS NOT NULL", (state_abb,))
    total = cur.fetchone()[0] or 0
    if total == 0: return 0.0
    
    # Matching distinct items
    cur.execute(f"""
    SELECT COUNT(DISTINCT l.{col_name}) 
    FROM {table_name} t
    JOIN lgd_directory l ON t.{join_col} = l.lgd_code::text 
    WHERE l.state_abb=%s AND l.{col_name} IS NOT NULL
    """, (state_abb,))
    match = cur.fetchone()[0] or 0
    
    return min(100.0, round((match / total) * 100, 2))

# Load Cache
with open('static/data/state_glance_cache.json', 'r') as f:
    cache = json.load(f)

for state in cache:
    print(f"Calculating true granular LGD coverage for {state}...")
    
    # SECC
    if "overview" in cache[state] and "secc" in cache[state]["overview"]:
        cache[state]["overview"]["secc"]["coverage_pct"] = {
            "districts": get_coverage('secc_abstract', state, 'district_code', 'lgd_code'),
            "villages": get_coverage('secc_abstract', state, 'village_code', 'lgd_code'),
            "wards": get_coverage('secc_abstract', state, 'ward_number', 'lgd_code'),
            "lgd_units": get_coverage('secc_abstract', state, 'lgd_code', 'lgd_code'),
            "blocks": get_coverage('secc_abstract', state, 'block_id', 'lgd_code'),
            "panchayats": get_coverage('secc_abstract', state, 'panchayat_id', 'lgd_code')
        }

    # EJAL
    if "overview" in cache[state] and "ejal" in cache[state]["overview"]:
        cache[state]["overview"]["ejal"]["coverage_pct"] = {
            "districts": get_coverage('ejalshakti_portal', state, 'district_code', 'lgd_code'),
            "villages": get_coverage('ejalshakti_portal', state, 'village_code', 'lgd_code'),
            "wards": get_coverage('ejalshakti_portal', state, 'ward_number', 'lgd_code'),
            "lgd_units": get_coverage('ejalshakti_portal', state, 'lgd_code', 'lgd_code'),
            "blocks": get_coverage('ejalshakti_portal', state, 'block_id', 'lgd_code'),
            "panchayats": get_coverage('ejalshakti_portal', state, 'panchayat_id', 'lgd_code')
        }

with open('static/data/state_glance_cache.json', 'w') as f:
    json.dump(cache, f, indent=2)

print("Finished fixing granular SECC/EJal coverage!")
