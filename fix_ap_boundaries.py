import json
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from app import get_rds_db

def fix_ap():
    with open('static/data/boundaries/AP.json', 'r', encoding='utf-8') as f:
        ap = json.load(f)

    telangana_districts = {
        'adilabad', 'hyderabad', 'karimnagar', 'khammam', 'mahbubnagar', 
        'medak', 'nalgonda', 'nizamabad', 'rangareddi', 'warangal'
    }

    norm = lambda s: (s or '').lower().replace(' ', '').replace('-', '').replace('_', '')

    ap_district_features = []
    for feat in ap.get('district_features', []):
        dname = feat.get('properties', {}).get('NAME_2', '')
        if norm(dname) not in telangana_districts:
            # Also normalize 'Vishakhapatnam' to 'Visakhapatnam' if desired, but keep properties clean
            feat['properties']['NAME_1'] = 'Andhra Pradesh'
            ap_district_features.append(feat)

    print(f"Original district features count: {len(ap.get('district_features', []))}")
    print(f"Filtered AP district features count: {len(ap_district_features)}")
    print("AP Districts retained:")
    for f in ap_district_features:
        print(" -", f['properties']['NAME_2'])

    # Merge into a single Andhra Pradesh state polygon
    geoms = [shape(f['geometry']) for f in ap_district_features]
    merged_state = unary_union(geoms)
    print("Merged AP boundary type:", merged_state.geom_type, "is_valid:", merged_state.is_valid)

    # Now get the EXACT AC-to-District mapping from the active RDS DB
    conn = get_rds_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.ac_no, a.ac_name, d.district_name
        FROM ac_mapping a
        LEFT JOIN district d ON a.district_id = d.district_id
        WHERE a.state_abb = 'AP'
        ORDER BY a.ac_no;
    """)
    db_acs = cur.fetchall()
    print(f"Fetched {len(db_acs)} ACs for AP from RDS DB.")

    # Build fresh ac_to_district mapping for AC 1 to 175
    new_ac_to_district = {}
    for ac_no, ac_name, dist_name in db_acs:
        new_ac_to_district[str(ac_no)] = dist_name

    ap['state_abb'] = 'AP'
    ap['state_feature'] = {
        'type': 'Feature',
        'properties': {
            'NAME_1': 'Andhra Pradesh',
            'ISO': 'IND-AP'
        },
        'geometry': mapping(merged_state)
    }
    ap['district_features'] = ap_district_features
    ap['ac_to_district'] = new_ac_to_district

    with open('static/data/boundaries/AP.json', 'w', encoding='utf-8') as f:
        json.dump(ap, f, indent=2)

    print("Successfully updated static/data/boundaries/AP.json with only Andhra Pradesh boundary and DB ac_to_district!")

def fix_ts():
    with open('static/data/boundaries/TS.json', 'r', encoding='utf-8') as f:
        ts = json.load(f)

    telangana_districts = {
        'adilabad', 'hyderabad', 'karimnagar', 'khammam', 'mahbubnagar', 
        'medak', 'nalgonda', 'nizamabad', 'rangareddi', 'warangal'
    }
    norm = lambda s: (s or '').lower().replace(' ', '').replace('-', '').replace('_', '')

    ts_features = [
        feat for feat in ts.get('district_features', [])
        if norm(feat.get('properties', {}).get('NAME_2')) in telangana_districts
    ]

    print("Original TS district features:", len(ts.get('district_features', [])))
    print("Retained Telangana features:", len(ts_features))

    geoms = [shape(f['geometry']) for f in ts_features]
    merged_state = unary_union(geoms)

    conn = get_rds_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.ac_no, a.ac_name, d.district_name
        FROM ac_mapping a
        LEFT JOIN district d ON a.district_id = d.district_id
        WHERE a.state_abb = 'TS'
        ORDER BY a.ac_no;
    """)
    db_acs = cur.fetchall()

    ts_ac_map = {}
    for ac_no, ac_name, dist_name in db_acs:
        ts_ac_map[str(ac_no)] = dist_name

    ts['state_abb'] = 'TS'
    ts['state_feature'] = {
        'type': 'Feature',
        'properties': {
            'NAME_1': 'Telangana',
            'ISO': 'IND-TS'
        },
        'geometry': mapping(merged_state)
    }
    ts['district_features'] = ts_features
    ts['ac_to_district'] = ts_ac_map

    with open('static/data/boundaries/TS.json', 'w', encoding='utf-8') as f:
        json.dump(ts, f, indent=2)

    print("Successfully updated static/data/boundaries/TS.json with only Telangana boundary and DB ac_to_district!")

if __name__ == '__main__':
    fix_ap()
    fix_ts()
