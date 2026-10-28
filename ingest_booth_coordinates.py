"""
Ingests 293,617 real booth coordinates from votexdb.booth_metadata_admin 
(accessible to neeharika_ka_de) into state_glance_cache.json.

Updates:
1. State-level Booth KPIs:
   - unique_coordinates
   - valid_coordinates
   - valid_coordinates_pct
   - geo_validation (valid vs invalid stacked bar breakdown)
   - map_pins (1 representative booth pin per AC for Leaflet map)
2. Requirement 1 Table (booth_details):
   - total_booth_coordinates
   - unique_booth_coordinates
   - valid_booth_coordinates
   - valid_booth_coordinates_pct
"""

import os
import json
import time
import psycopg2

def ingest_coordinates():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Connecting to votexdb as neeharika_ka_de...")
    t0 = time.time()
    
    conn = psycopg2.connect(
        host="org-db.cgtvjodbp1rf.ap-south-1.rds.amazonaws.com",
        port=5432,
        user="neeharika_ka_de",
        password="dvhbdaybndkfkj1274nd",
        dbname="votexdb",
        connect_timeout=30
    )
    cur = conn.cursor()
    
    # ─── 1. Query State-level Coordinates Aggregates ──────────────────────────
    print("[1/4] Querying State-level Coordinate Aggregates...")
    cur.execute("""
    SELECT 
        b.state_abb,
        COUNT(*) as total_booths,
        COUNT(a.booth_latitude) as total_coords,
        COUNT(DISTINCT CASE WHEN a.booth_latitude IS NOT NULL AND a.booth_longitude IS NOT NULL THEN CONCAT(ROUND(a.booth_latitude::numeric, 6), ',', ROUND(a.booth_longitude::numeric, 6)) END) as unique_coords,
        COUNT(CASE WHEN a.booth_latitude BETWEEN 6.0 AND 38.0 AND a.booth_longitude BETWEEN 68.0 AND 98.0 THEN 1 END) as valid_coords
    FROM booth_metadata b
    JOIN booth_metadata_admin a ON b.el_booth_id = a.el_booth_id
    GROUP BY b.state_abb;
    """)
    state_coords = {}
    for r in cur.fetchall():
        s_abb, tot_b, tot_c, unq_c, val_c = r
        if s_abb == 'CG':
            s_abb = 'CH'
        pct = round((val_c / tot_b) * 100, 1) if tot_b else 0.0
        state_coords[s_abb] = {
            'total_booths': tot_b,
            'total_coords': tot_c,
            'unique_coords': unq_c,
            'valid_coords': val_c,
            'valid_pct': pct,
            'invalid_coords': max(tot_b - val_c, 0)
        }
    print(f"  Processed {len(state_coords)} states.")
    for s_abb, sc in state_coords.items():
        if sc['total_coords'] > 0:
            print(f"    {s_abb}: {sc['total_coords']:,} coords, {sc['unique_coords']:,} unique, {sc['valid_coords']:,} valid ({sc['valid_pct']}%)")

    # ─── 2. Query AC-level Coordinates Aggregates ─────────────────────────────
    print("[2/4] Querying AC-level Coordinate Aggregates (Requirement 1)...")
    cur.execute("""
    SELECT 
        b.state_abb,
        b.ac_no,
        COUNT(a.booth_latitude) as total_coords,
        COUNT(DISTINCT CASE WHEN a.booth_latitude IS NOT NULL AND a.booth_longitude IS NOT NULL THEN CONCAT(ROUND(a.booth_latitude::numeric, 6), ',', ROUND(a.booth_longitude::numeric, 6)) END) as unique_coords,
        COUNT(CASE WHEN a.booth_latitude BETWEEN 6.0 AND 38.0 AND a.booth_longitude BETWEEN 68.0 AND 98.0 THEN 1 END) as valid_coords
    FROM booth_metadata b
    JOIN booth_metadata_admin a ON b.el_booth_id = a.el_booth_id
    GROUP BY b.state_abb, b.ac_no;
    """)
    ac_coords = {}
    for r in cur.fetchall():
        s_abb, ac_no, tot_c, unq_c, val_c = r
        if s_abb == 'CG':
            s_abb = 'CH'
        if s_abb not in ac_coords:
            ac_coords[s_abb] = {}
        pct = round((val_c / max(tot_c, 1)) * 100, 1) if tot_c > 0 else 0.0
        ac_coords[s_abb][ac_no] = {
            'total_booth_coordinates': tot_c if tot_c > 0 else None,
            'unique_booth_coordinates': unq_c if tot_c > 0 else None,
            'valid_booth_coordinates': val_c if tot_c > 0 else None,
            'valid_booth_coordinates_pct': pct if tot_c > 0 else None
        }
    print(f"  Processed {sum(len(acs) for acs in ac_coords.values())} AC coordinate records.")

    # ─── 3. Query Spatial Map Pins (1 per AC for Interactive Leaflet Map) ─────
    print("[3/4] Querying Representative Booth Map Pins per AC...")
    cur.execute("""
    SELECT 
        b.state_abb,
        b.ac_no,
        COALESCE(m.ac_name, CONCAT('AC ', b.ac_no)) as ac_name,
        b.booth_no,
        b.booth_name,
        a.booth_latitude,
        a.booth_longitude
    FROM (
        SELECT 
            b.el_booth_id,
            b.state_abb,
            b.ac_no,
            b.booth_no,
            b.booth_name,
            ROW_NUMBER() OVER (PARTITION BY b.state_abb, b.ac_no ORDER BY b.el_booth_id) as rn
        FROM booth_metadata b
        JOIN booth_metadata_admin a ON b.el_booth_id = a.el_booth_id
        WHERE a.booth_latitude BETWEEN 6.0 AND 38.0 AND a.booth_longitude BETWEEN 68.0 AND 98.0
    ) b
    JOIN booth_metadata_admin a ON b.el_booth_id = a.el_booth_id
    LEFT JOIN ac_mapping m ON b.state_abb = m.state_abb AND b.ac_no = m.ac_no
    WHERE b.rn = 1;
    """)
    state_pins = {}
    for r in cur.fetchall():
        s_abb, ac_no, ac_name, b_no, b_name, lat, lng = r
        if s_abb == 'CG':
            s_abb = 'CH'
        if s_abb not in state_pins:
            state_pins[s_abb] = []
        state_pins[s_abb].append({
            'ac_no': ac_no,
            'ac_name': ac_name,
            'booth_no': b_no,
            'booth_name': b_name,
            'lat': round(float(lat), 5),
            'lng': round(float(lng), 5)
        })
    print(f"  Extracted map pins for {len(state_pins)} states: { {k: len(v) for k, v in state_pins.items()} }")
    conn.close()

    # ─── 4. Update state_glance_cache.json ─────────────────────────────────────
    print("[4/4] Updating state_glance_cache.json with real coordinates...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_path = os.path.join(base_dir, 'static', 'data', 'state_glance_cache.json')
    
    with open(cache_path, 'r', encoding='utf-8') as f:
        cache_data = json.load(f)

    updated_states = 0
    updated_ac_rows = 0

    for s_abb, st_data in cache_data.items():
        if 'booth' not in st_data or not isinstance(st_data['booth'], dict):
            continue

        b_obj = st_data['booth']
        sc = state_coords.get(s_abb)

        if sc and sc['total_coords'] > 0:
            b_obj['unique_coordinates'] = sc['unique_coords']
            b_obj['valid_coordinates'] = sc['valid_coords']
            b_obj['valid_coordinates_pct'] = sc['valid_pct']
            b_obj['geo_validation'] = {
                'valid': sc['valid_coords'],
                'invalid': sc['invalid_coords'],
                'validation_pct': sc['valid_pct'],
                'status': 'Verified'
            }
            b_obj['map_pins'] = state_pins.get(s_abb, [])
            updated_states += 1
        else:
            # Leave as None for clean missing-state display
            b_obj['unique_coordinates'] = None
            b_obj['valid_coordinates'] = None
            b_obj['valid_coordinates_pct'] = None
            b_obj['geo_validation'] = None
            b_obj['map_pins'] = []

        # Update each AC row in booth_details (Requirement 1 Table)
        details_list = b_obj.get('booth_details', [])
        ac_map = ac_coords.get(s_abb, {})
        for row in details_list:
            ac_num = row.get('ac_no')
            ac_stat = ac_map.get(ac_num)
            if ac_stat and ac_stat['total_booth_coordinates'] is not None:
                row['total_booth_coordinates'] = ac_stat['total_booth_coordinates']
                row['unique_booth_coordinates'] = ac_stat['unique_booth_coordinates']
                row['valid_booth_coordinates'] = ac_stat['valid_booth_coordinates']
                row['valid_booth_coordinates_pct'] = ac_stat['valid_booth_coordinates_pct']
                updated_ac_rows += 1
            else:
                row['total_booth_coordinates'] = None
                row['unique_booth_coordinates'] = None
                row['valid_booth_coordinates'] = None
                row['valid_booth_coordinates_pct'] = None

    # Write updated state_glance_cache.json
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, indent=2)
    print(f"  Successfully wrote {cache_path} ({updated_states} states with coords, {updated_ac_rows} AC rows updated).")

    # Also update backup/fixed cache files
    for backup_name in ['state_glance_cache_fixed.json', 'scratch_state_glance_cache.json']:
        p = os.path.join(base_dir, backup_name)
        if os.path.exists(p):
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)

    # Sync to Redis if available
    rc = None
    try:
        from app import get_redis
        rc = get_redis()
        if rc:
            for s_abb, st_data in cache_data.items():
                rc.set(f'state_glance:{s_abb}', json.dumps(st_data))
            print("  Synchronized updated states to Redis.")
    except Exception as e:
        print(f"  [Note] Redis sync skipped ({e}).")

    # Also update Country Glance Cache (glance_cache.json) and push to Redis dynamically
    glance_path = os.path.join(base_dir, 'static', 'data', 'glance_cache.json')
    if os.path.exists(glance_path):
        try:
            with open(glance_path, 'r', encoding='utf-8') as f:
                glance_data = json.load(f)
            matrix = glance_data.get('matrix', [])
            for row in matrix:
                abb = row.get('state_abb')
                st_key = 'CH' if abb == 'CG' else ('CG' if abb == 'CT' else abb)
                st_info = cache_data.get(st_key) or cache_data.get(abb) or {}
                st_b = st_info.get('booth') or {}
                st_v = st_info.get('voter') or {}
                v_pct = st_b.get('valid_coordinates_pct')
                c_pct = round(float(v_pct), 2) if v_pct is not None else 0.0
                row['coordinates'] = c_pct
                row['voter'] = c_pct
                row['valid_coordinates'] = st_b.get('valid_coordinates') or 0
                row['total_voters'] = st_v.get('total_voters') or 0
                row['gender_ratio'] = st_v.get('gender_ratio') or 0
                row['total_booths'] = st_b.get('total_booths') or row.get('total_booths', 0)
            
            nav = glance_data.get('national_avg', {})
            coord_avg = round(sum(r.get('coordinates', 0) for r in matrix) / max(len(matrix), 1), 2)
            nav['coordinates'] = coord_avg
            nav['voter'] = coord_avg
            glance_data['national_avg'] = nav
            
            with open(glance_path, 'w', encoding='utf-8') as f:
                json.dump(glance_data, f, indent=2)
            print(f"  Synchronized Country Glance cache with coordinates (National Avg: {coord_avg}%).")
            
            if rc:
                rc.set('cache:country_glance_data:data', json.dumps(glance_data))
                print("  Synchronized country_glance_data to Redis.")
        except Exception as ge:
            print(f"  [WARN] Failed to update country glance cache: {ge}")

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Ingestion complete in {round(time.time() - t0, 1)}s!")
    return True

if __name__ == '__main__':
    ingest_coordinates()
