import os
import json
import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# Canonical AC Counts from app.py
STATE_AC_COUNTS = {
    'AP': 175, 'AR': 60, 'AS': 126, 'BR': 243, 'CG': 90, 'GA': 40, 'GJ': 182,
    'HR': 90, 'HP': 68, 'JK': 90, 'JH': 81, 'KA': 224, 'KL': 140, 'MP': 230,
    'MH': 288, 'MN': 60, 'ML': 60, 'MZ': 40, 'NL': 60, 'OR': 147, 'PB': 117,
    'RJ': 200, 'SK': 32, 'TN': 234, 'TS': 119, 'TR': 60, 'UP': 403, 'UK': 70,
    'WB': 294, 'AN': 1, 'CH': 1, 'DN': 1, 'DD': 1, 'DL': 70, 'LD': 1, 'PY': 30
}

# Canonical State Names
STATE_NAMES = {
    'AN': 'Andaman & Nicobar Islands', 'AP': 'Andhra Pradesh', 'AR': 'Arunachal Pradesh',
    'AS': 'Assam', 'BR': 'Bihar', 'CH': 'Chandigarh', 'CT': 'Chhattisgarh',
    'DD': 'Daman & Diu', 'DL': 'Delhi', 'DN': 'Dadra and Nagar Haveli', 'GA': 'Goa',
    'GJ': 'Gujarat', 'HP': 'Himachal Pradesh', 'HR': 'Haryana', 'JH': 'Jharkhand',
    'JK': 'Jammu & Kashmir', 'KA': 'Karnataka', 'KL': 'Kerala', 'LA': 'Ladakh',
    'LD': 'Lakshadweep', 'MH': 'Maharashtra', 'ML': 'Meghalaya', 'MN': 'Manipur',
    'MP': 'Madhya Pradesh', 'MZ': 'Mizoram', 'NL': 'Nagaland', 'OR': 'Odisha',
    'PB': 'Punjab', 'PY': 'Puducherry', 'RJ': 'Rajasthan', 'SK': 'Sikkim',
    'TN': 'Tamil Nadu', 'TR': 'Tripura', 'TS': 'Telangana', 'UK': 'Uttarakhand',
    'UP': 'Uttar Pradesh', 'WB': 'West Bengal'
}

print("Connecting to DB...")
conn = psycopg2.connect(
    host=os.environ.get('DB_HOST'),
    port=os.environ.get('DB_PORT', '5432'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD'),
    dbname=os.environ.get('DB_NAME')
)
print("Connected!")

cur = conn.cursor()

# 1. Retro
print("Executing Retro Expected query...")
cur.execute("""
    SELECT state_abb, COUNT(DISTINCT (el_year, el_type, ac_no)) 
    FROM ac_election_mapping 
    WHERE el_type NOT LIKE '%BP%'
    GROUP BY state_abb;
""")
expected_retro = {r[0]: r[1] for r in cur.fetchall()}

print("Executing Retro Available query (this might take a while)...")
cur.execute("""
    SELECT er.state_abb, COUNT(DISTINCT (e.el_year, e.el_type, er.ac_no)) 
    FROM election_result er
    JOIN election e ON e.el_id = er.el_id
    WHERE e.el_type NOT LIKE '%BP%'
    GROUP BY er.state_abb;
""")
available_retro = {r[0]: r[1] for r in cur.fetchall()}

# 2. Form 20
print("Executing Form 20 Expected query...")
cur.execute("""
    SELECT state_abb, COUNT(DISTINCT (el_year, el_type, ac_no)) 
    FROM ac_election_mapping
    WHERE el_type NOT LIKE '%BP%'
    GROUP BY state_abb;
""")
expected_f20 = {r[0]: r[1] for r in cur.fetchall()}

print("Executing Form 20 Available query (this might take a while)...")
cur.execute("""
    SELECT state_abb, COUNT(DISTINCT (el_year, el_type, ac_no)) 
    FROM form20_summary_view
    WHERE el_type NOT LIKE '%BP%'
    GROUP BY state_abb;
""")
available_f20 = {r[0]: r[1] for r in cur.fetchall()}

# 3. Caste Data
print("Executing Caste Data query...")
cur.execute("""
    SELECT state_abb, COUNT(DISTINCT ac_no) 
    FROM caste_details 
    GROUP BY state_abb;
""")
available_caste = {r[0]: r[1] for r in cur.fetchall()}

# 4. Booth Details
print("Executing Booth Details query...")
cur.execute("""
    SELECT state_abb, COUNT(DISTINCT ac_no) 
    FROM booth_metadata_full_view 
    GROUP BY state_abb;
""")
available_booth = {r[0]: r[1] for r in cur.fetchall()}

# 5. Denominators from LGD
print("Executing LGD Denominators queries...")
cur.execute("SELECT state_abb, COUNT(DISTINCT district_code) FROM lgd_directory GROUP BY state_abb;")
lgd_districts = {r[0]: r[1] for r in cur.fetchall()}

cur.execute("SELECT state_abb, COUNT(DISTINCT lgd_code) FROM lgd_directory GROUP BY state_abb;")
lgd_codes = {r[0]: r[1] for r in cur.fetchall()}

# Other source counts
print("Executing Muslim Census query...")
cur.execute("SELECT state_abb, COUNT(DISTINCT district_name) FROM muslim_census GROUP BY state_abb;")
muslim_counts = {r[0]: r[1] for r in cur.fetchall()}

print("Executing Joshua Population query...")
cur.execute("SELECT state_abb, COUNT(DISTINCT district_name) FROM joshua_population GROUP BY state_abb;")
joshua_counts = {r[0]: r[1] for r in cur.fetchall()}

print("Executing Ejalshakti query...")
cur.execute("SELECT ld.state_abb, COUNT(DISTINCT ep.lgd_code) FROM ejalshakti_portal ep JOIN lgd_directory ld ON ld.lgd_code = ep.lgd_code GROUP BY ld.state_abb;")
ejal_counts = {r[0]: r[1] for r in cur.fetchall()}

print("Executing SECC query...")
cur.execute("SELECT state_abb, COUNT(DISTINCT lgd_code) FROM secc_abstract GROUP BY state_abb;")
secc_counts = {r[0]: r[1] for r in cur.fetchall()}

print("Executing KYS query...")
cur.execute("SELECT state_abb, COUNT(DISTINCT district_name) FROM school_locator WHERE district_name IS NOT NULL GROUP BY state_abb;")
kys_counts = {r[0]: r[1] for r in cur.fetchall()}

print("Building matrix...")

matrix = []
for abb, name in STATE_NAMES.items():
    # Retro %
    exp_r = expected_retro.get(abb, 0)
    av_r = available_retro.get(abb, 0)
    retro_pct = (av_r / exp_r * 100.0) if exp_r else 0.0
    if retro_pct > 100.0:
        retro_pct = 100.0
        
    # Form 20 %
    exp_f = expected_f20.get(abb, 0)
    av_f = available_f20.get(abb, 0)
    f20_pct = (av_f / exp_f * 100.0) if exp_f else 0.0
    
    # Caste Data %
    total_ac = STATE_AC_COUNTS.get(abb, 1)
    caste_pct = (available_caste.get(abb, 0) / total_ac * 100.0)
    if caste_pct > 100.0:
        caste_pct = 100.0
        
    # Booth Details %
    booth_pct = (available_booth.get(abb, 0) / total_ac * 100.0)
    if booth_pct > 100.0:
        booth_pct = 100.0
        
    # LGD Districts
    lgd_d = lgd_districts.get(abb, 0)
    lgd_c = lgd_codes.get(abb, 0)
    
    # Muslim %
    muslim_pct = (muslim_counts.get(abb, 0) / lgd_d * 100.0) if lgd_d else 0.0
    # Joshua %
    joshua_pct = (joshua_counts.get(abb, 0) / lgd_d * 100.0) if lgd_d else 0.0
    # KYS %
    kys_pct = (kys_counts.get(abb, 0) / lgd_d * 100.0) if lgd_d else 0.0
    # LGD % (Assuming lgd completion is based on whether district data is populated vs LGD directory counts)
    lgd_pct = 100.0 if lgd_d > 0 else 0.0
    # Ejalshakti %
    ejal_pct = (ejal_counts.get(abb, 0) / lgd_c * 100.0) if lgd_c else 0.0
    # SECC %
    secc_pct = (secc_counts.get(abb, 0) / lgd_c * 100.0) if lgd_c else 0.0
    
    # Missing Tables (NREGA, Indiastat, Election Lens) return 0.0 as there is no DB table yet
    nrega_pct = 0.0
    indiastat_pct = 0.0
    lens_pct = 0.0
        
    row = {
        "state_abb": abb,
        "state_name": name,
        "retro": round(retro_pct, 2),
        "form20": round(f20_pct, 2),
        "caste": round(caste_pct, 2),
        "booth": round(booth_pct, 2),
        "muslim": round(muslim_pct, 2),
        "joshua": round(joshua_pct, 2),
        "kys": round(kys_pct, 2),
        "lgd": round(lgd_pct, 2),
        "ejal": round(ejal_pct, 2),
        "secc": round(secc_pct, 2),
        "nrega": round(nrega_pct, 2),
        "indiastat": round(indiastat_pct, 2),
        "lens": round(lens_pct, 2)
    }
    matrix.append(row)

# Calculate national averages
def avg_field(m, field):
    vals = [r[field] for r in m]
    return round(sum(vals) / len(vals), 2)

out_data = {
    "success": True,
    "national_avg": {
        "retro": avg_field(matrix, 'retro'),
        "form20": avg_field(matrix, 'form20'),
        "caste": avg_field(matrix, 'caste'),
        "booth": avg_field(matrix, 'booth'),
        "muslim": avg_field(matrix, 'muslim'),
        "joshua": avg_field(matrix, 'joshua'),
        "kys": avg_field(matrix, 'kys'),
        "lgd": avg_field(matrix, 'lgd'),
        "ejal": avg_field(matrix, 'ejal'),
        "secc": avg_field(matrix, 'secc'),
        "nrega": avg_field(matrix, 'nrega'),
        "indiastat": avg_field(matrix, 'indiastat'),
        "lens": avg_field(matrix, 'lens')
    },
    "matrix": sorted(matrix, key=lambda x: x['state_name'])
}

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'data', 'glance_cache.json')
with open(out_path, "w") as f:
    json.dump(out_data, f, indent=2)

print("Calculation successful!")
cur.close()
conn.close()
