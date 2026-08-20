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

# Query the true zone populations for ALL states using AC-level fractional distribution
query = """
WITH dist_pop AS (
    SELECT state_abb, LOWER(district_name) as dname, SUM(total_population) as pop 
    FROM joshua_population GROUP BY state_abb, LOWER(district_name)
),
ac_dist AS (
    SELECT a.ac_id, a.state_abb, LOWER(d.district_name) as dname, a.zone_id
    FROM ac_mapping a
    JOIN district d ON a.district_id = d.district_id
),
dist_ac_count AS (
    SELECT state_abb, dname, COUNT(ac_id) as ac_cnt
    FROM ac_dist GROUP BY state_abb, dname
),
ac_pop AS (
    SELECT a.ac_id, a.state_abb, a.zone_id, (dp.pop / NULLIF(dac.ac_cnt, 0)) as pop_per_ac
    FROM ac_dist a
    JOIN dist_pop dp ON a.dname = dp.dname AND a.state_abb = dp.state_abb
    JOIN dist_ac_count dac ON a.dname = dac.dname AND a.state_abb = dac.state_abb
)
SELECT ap.state_abb, COALESCE(z.zone_name, 'Null') as zone_name, SUM(ap.pop_per_ac)
FROM ac_pop ap
LEFT JOIN zone z ON ap.zone_id = z.zone_id
GROUP BY ap.state_abb, COALESCE(z.zone_name, 'Null');
"""

print("Executing AC-weighted true zone population aggregation...")
cur.execute(query)
results = cur.fetchall()

# Organize by state
state_zones = {}
for state_abb, zone_name, pop in results:
    if not pop: continue
    if state_abb not in state_zones:
        state_zones[state_abb] = []
    state_zones[state_abb].append({"zone": zone_name, "pop": int(pop)})

# Add population from districts that didn't join to any AC at all (Unmapped)
query_unmapped = """
WITH mapped_dists AS (
    SELECT DISTINCT a.state_abb, LOWER(d.district_name) as dname
    FROM ac_mapping a JOIN district d ON a.district_id = d.district_id
)
SELECT j.state_abb, SUM(j.total_population) 
FROM joshua_population j
LEFT JOIN mapped_dists md ON LOWER(j.district_name) = md.dname AND j.state_abb = md.state_abb
WHERE md.dname IS NULL
GROUP BY j.state_abb;
"""
cur.execute(query_unmapped)
unmapped = cur.fetchall()
for state_abb, pop in unmapped:
    if pop and pop > 0:
        if state_abb not in state_zones: state_zones[state_abb] = []
        
        # Add to existing 'Null' or create new 'Null'
        null_zone = next((z for z in state_zones[state_abb] if z["zone"] == 'Null'), None)
        if null_zone: null_zone["pop"] += int(pop)
        else: state_zones[state_abb].append({"zone": "Null", "pop": int(pop)})

# Calculate percentages and sort
for state in state_zones:
    total_pop = sum(z["pop"] for z in state_zones[state])
    if total_pop > 0:
        for z in state_zones[state]:
            z["pct"] = round((z["pop"] / total_pop) * 100, 2)
    # Sort by population descending
    state_zones[state].sort(key=lambda x: x["pop"], reverse=True)

# Update the cache
with open('static/data/state_glance_cache.json', 'r') as f:
    cache = json.load(f)

for state in cache:
    if "demographics" in cache[state]:
        if state in state_zones:
            cache[state]["demographics"]["zone_distribution"] = state_zones[state]
        else:
            cache[state]["demographics"]["zone_distribution"] = []

with open('static/data/state_glance_cache.json', 'w') as f:
    json.dump(cache, f, indent=2)

print("Finished fixing AC-weighted true zones!")
