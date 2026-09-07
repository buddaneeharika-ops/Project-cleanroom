import json
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('c:/Users/neeha/OneDrive/Desktop/Work/Form20_Dashboard_Release/.env')
conn = psycopg2.connect(host=os.environ['DB_HOST'], port=os.environ['DB_PORT'], user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'], dbname=os.environ['DB_NAME'])
cur = conn.cursor()

# Get true expected counts directly from the DB (Excluding by-polls!)
cur.execute("SELECT state_abb, COUNT(DISTINCT (el_year, el_type, ac_no)) FROM ac_election_mapping WHERE el_type NOT LIKE '%BP%' GROUP BY state_abb;")
expected_f20 = {r[0]: r[1] for r in cur.fetchall()}

cur.execute("SELECT state_abb, COUNT(DISTINCT (el_year, el_type, ac_no)) FROM form20_summary_view WHERE el_type NOT LIKE '%BP%' GROUP BY state_abb;")
available_f20 = {r[0]: r[1] for r in cur.fetchall()}

# Load the local cache
with open('c:/Users/neeha/OneDrive/Desktop/Work/Form20_Dashboard_Release/scratch_state_glance_cache.json', 'r', encoding='utf-8') as f:
    cache = json.load(f)

# Patch ALL states instantly!
for state, data in cache.items():
    if state not in expected_f20: continue
    
    exp_f = expected_f20.get(state, 0)
    av_f = available_f20.get(state, 0)
    
    true_pct = round((av_f / exp_f * 100.0) if exp_f > 0 else 0, 2)
    if true_pct > 100.0: true_pct = 100.0
    
    if "form20" not in data: data["form20"] = {}
    data["form20"]["availability_pct"] = true_pct
    
    # Also fix Retro just in case!
    cur.execute("SELECT COUNT(DISTINCT (el_year, el_type, ac_no)) FROM election_result er JOIN election e ON e.el_id = er.el_id WHERE e.el_type NOT LIKE '%BP%' AND er.state_abb = %s", (state,))
    av_retro = cur.fetchone()[0]
    retro_pct = round((av_retro / exp_f * 100.0) if exp_f > 0 else 0, 2)
    if retro_pct > 100.0: retro_pct = 100.0
    
    if "hero" not in data: data["hero"] = {}
    data["hero"]["retro_availability_pct"] = retro_pct

with open('c:/Users/neeha/OneDrive/Desktop/Work/Form20_Dashboard_Release/patched_state_glance.json', 'w', encoding='utf-8') as f:
    json.dump(cache, f, indent=2)

print("Patching complete! Ready to upload and push to Redis!")
