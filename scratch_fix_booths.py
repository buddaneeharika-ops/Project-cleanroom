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

print("Querying true booth counts per state from booth_metadata_full_view...")
cur.execute("SELECT state_abb, COUNT(DISTINCT (ac_no, booth_no)) FROM booth_metadata_full_view GROUP BY state_abb")
booth_counts = dict(cur.fetchall())
print(booth_counts)

with open('static/data/state_glance_cache.json', 'r') as f:
    cache = json.load(f)

for state in cache:
    if "form20" in cache[state]:
        # Fallback to an estimate (e.g. 280 booths per AC) if the state has no booths in the view
        actual = booth_counts.get(state)
        if not actual:
            actual = cache[state].get("hero", {}).get("total_acs", 100) * 280
        cache[state]["form20"]["total_booths"] = actual

with open('static/data/state_glance_cache.json', 'w') as f:
    json.dump(cache, f, indent=2)
print("Updated all states in JSON cache.")
