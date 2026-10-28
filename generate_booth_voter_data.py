import os
import json
import time
from app import get_rds_db, STATE_NAMES, STATE_AC_COUNTS, get_redis

def generate_booth_voter_data():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting Booth Metadata & Voter Details Aggregation (DB-ONLY Mode)...")
    t0 = time.time()
    
    conn = get_rds_db()
    if not conn:
        print("[ERROR] Could not connect to RDS database.")
        return False
        
    cur = conn.cursor()
    
    # ─── 1. Query State & Zone Aggregates ─────────────────────────────────────
    print("[1/5] Querying Zone-level Booth and Voter aggregations from RDS...")
    zone_query = """
    SELECT 
        b.state_abb,
        COALESCE(z.zone_name, 'General') AS zone_name,
        COUNT(DISTINCT b.district) AS district_count,
        COUNT(*) AS total_booths,
        COUNT(DISTINCT b.ac_no) AS ac_count,
        COUNT(CASE WHEN (b.block IS NOT NULL AND b.block != '') OR (b.taluka IS NOT NULL AND b.taluka != '') OR (b.tehsil IS NOT NULL AND b.tehsil != '') THEN 1 END) AS block_count,
        COUNT(CASE WHEN (b.panchayat IS NOT NULL AND b.panchayat != '') OR (b.ward_no IS NOT NULL AND b.ward_no != '') THEN 1 END) AS panchayat_count,
        COUNT(CASE WHEN b.police_station IS NOT NULL AND b.police_station != '' THEN 1 END) AS police_stn_count,
        COUNT(CASE WHEN b.pincode IS NOT NULL AND b.pincode != '' THEN 1 END) AS pincode_count,
        COUNT(CASE WHEN b.booth_address IS NOT NULL AND b.booth_address != '' THEN 1 END) AS address_count,
        COALESCE(SUM(b.total_voters), 0) AS total_voters,
        COALESCE(SUM(b.male_voters), 0) AS male_voters,
        COALESCE(SUM(b.female_voters), 0) AS female_voters
    FROM booth_metadata_full_view b
    LEFT JOIN ac_mapping a ON b.state_abb = a.state_abb AND b.ac_no = a.ac_no
    LEFT JOIN zone z ON a.zone_id = z.zone_id
    GROUP BY b.state_abb, COALESCE(z.zone_name, 'General')
    ORDER BY b.state_abb, total_booths DESC;
    """
    cur.execute(zone_query)
    zone_rows = cur.fetchall()
    
    state_zone_map = {}
    for r in zone_rows:
        s_abb, z_name, dist_cnt, b_cnt, ac_cnt, blk_cnt, pan_cnt, ps_cnt, pin_cnt, addr_cnt, tot_v, m_v, f_v = r
        if s_abb == 'CG':
            s_abb = 'CH'
        if s_abb not in state_zone_map:
            state_zone_map[s_abb] = []
            
        b_pct = round((blk_cnt / max(b_cnt, 1)) * 100, 1)
        pan_pct = round((pan_cnt / max(b_cnt, 1)) * 100, 1)
        ps_pct = round((ps_cnt / max(b_cnt, 1)) * 100, 1)
        pin_pct = round((pin_cnt / max(b_cnt, 1)) * 100, 1)
        addr_pct = round((addr_cnt / max(b_cnt, 1)) * 100, 1)
        avail_pct = round((b_pct + pan_pct + ps_pct + pin_pct) / 4.0, 1)
        g_ratio = round((f_v / max(m_v, 1)) * 1000) if m_v > 0 else 0
        avg_v_b = round(tot_v / max(b_cnt, 1)) if b_cnt > 0 else 0
        
        state_zone_map[s_abb].append({
            'zone': z_name,
            'districts': dist_cnt,
            'total_booths': b_cnt,
            'total_voters': tot_v,
            'male_voters': m_v,
            'female_voters': f_v,
            'gender_ratio': g_ratio,
            'avg_voters_per_booth': avg_v_b,
            'block_pct': b_pct,
            'panchayat_pct': pan_pct,
            'police_stn_pct': ps_pct,
            'pincode_pct': pin_pct,
            'address_pct': addr_pct,
            'avail_pct': avail_pct
        })

    # ─── 2. Query AC-level Aggregates (Requirement 1: Add Booth Details) ───────
    print("[2/5] Querying AC-level Booth Details from RDS (booth_metadata_full_view)...")
    ac_query = """
    SELECT 
        b.state_abb,
        b.ac_no,
        COALESCE(a.ac_name, CONCAT('AC-', b.ac_no)) AS ac_name,
        COUNT(*) AS extracted_booths,
        GREATEST(COUNT(*), COALESCE(MAX(CAST(NULLIF(regexp_replace(b.booth_no, '\\D', '', 'g'), '') AS integer)), COUNT(*))) AS actual_booths,
        COALESCE(SUM(b.total_voters), 0) AS total_voters,
        COALESCE(SUM(b.male_voters), 0) AS male_voters,
        COALESCE(SUM(b.female_voters), 0) AS female_voters,
        COUNT(DISTINCT b.district) AS district_count,
        COUNT(DISTINCT COALESCE(NULLIF(b.block, ''), NULLIF(b.taluka, ''), NULLIF(b.tehsil, ''), NULLIF(b.prakhand, ''), NULLIF(b.anchal, ''))) AS block_count,
        COUNT(DISTINCT COALESCE(NULLIF(b.panchayat, ''), NULLIF(b.ward_no, ''))) AS panchayat_count,
        COUNT(DISTINCT NULLIF(b.police_station, '')) AS ps_count,
        COUNT(CASE WHEN b.police_station IS NULL OR b.police_station = '' THEN 1 END) AS missing_ps,
        COUNT(CASE WHEN b.pincode IS NULL OR b.pincode = '' THEN 1 END) AS missing_pincode,
        COUNT(CASE WHEN 
            (b.block IS NULL OR b.block = '') AND 
            (b.taluka IS NULL OR b.taluka = '') AND 
            (b.tehsil IS NULL OR b.tehsil = '') AND 
            (b.sub_division IS NULL OR b.sub_division = '') AND
            (b.prakhand IS NULL OR b.prakhand = '') AND
            (b.anchal IS NULL OR b.anchal = '') AND
            (b.anumandal IS NULL OR b.anumandal = '')
        THEN 1 END) AS missing_subadmin,
        COALESCE(MAX(b.district), MAX(d.district_name), '') AS district_name
    FROM booth_metadata_full_view b
    LEFT JOIN ac_mapping a ON b.state_abb = a.state_abb AND b.ac_no = a.ac_no
    LEFT JOIN district d ON a.district_id = d.district_id
    GROUP BY b.state_abb, b.ac_no, a.ac_name
    ORDER BY b.state_abb, b.ac_no;
    """
    cur.execute(ac_query)
    ac_rows = cur.fetchall()
    
    state_acs_map = {}
    state_booth_details = {}
    
    for r in ac_rows:
        s_abb, ac_no, ac_name, b_cnt, act_cnt, tot_v, m_v, f_v, dist_cnt, blk_cnt, pan_cnt, ps_cnt, mis_ps, mis_pin, mis_sub, dist_name = r
        if s_abb == 'CG':
            s_abb = 'CH'
        if s_abb not in state_acs_map:
            state_acs_map[s_abb] = []
        if s_abb not in state_booth_details:
            state_booth_details[s_abb] = []
            
        tot_missing = mis_ps + mis_pin + mis_sub
        missing_rate = (tot_missing / max(b_cnt * 3, 1)) * 100
        impact = 'Critical Gaps' if missing_rate > 30 or mis_ps > 50 else ('Moderate Gaps' if missing_rate > 10 or mis_ps > 10 else 'Complete')
        
        # Requirement 1 Record:
        # 'actual_booths': Real gazetted max serial booth count / extracted count.
        # Coordinates (total, unique, valid, valid_pct) are None because lat/long is NOT in RDS DB.
        state_booth_details[s_abb].append({
            'state': s_abb,
            'ac_no': ac_no,
            'ac_name': ac_name,
            'district': dist_name,
            'actual_booths': act_cnt,  # Real count from max serial booth / extracted
            'extracted_booths': b_cnt,  # Real count from booth_metadata_full_view
            'total_blocks': blk_cnt if blk_cnt > 0 else 0,
            'total_panchayat': pan_cnt if pan_cnt > 0 else 0,
            'total_police_station': ps_cnt if ps_cnt > 0 else 0,
            'total_districts': dist_cnt if dist_cnt > 0 else 0,
            'total_booth_coordinates': None,   # Not in DB -> '—'
            'unique_booth_coordinates': None,  # Not in DB -> '—'
            'valid_booth_coordinates': None,   # Not in DB -> '—'
            'valid_booth_coordinates_pct': None, # Not in DB -> '—'
            'missing_data_status': impact,
            'total_voters': tot_v,
            'male_voters': m_v,
            'female_voters': f_v,
            'missing_ps': mis_ps,
            'missing_pincode': mis_pin,
            'missing_subadmin': mis_sub,
            'total_missing': tot_missing
        })

        state_acs_map[s_abb].append({
            'ac_no': ac_no,
            'ac_name': ac_name,
            'district': dist_name,
            'total_booths': b_cnt,
            'total_voters': tot_v,
            'male_voters': m_v,
            'female_voters': f_v,
            'missing_ps': mis_ps,
            'missing_pincode': mis_pin,
            'missing_subadmin': mis_sub,
            'total_missing': tot_missing,
            'impact': 'Critical' if 'Critical' in impact else ('Moderate' if 'Moderate' in impact else 'Low')
        })

    # ─── 3. Query Polling Station Granular Rows (Requirement 2: Booth_Voter Details) ──
    print("[3/5] Querying Granular Polling Station Rows for Booth_Voter Details...")
    booth_query = """
    WITH ranked_booths AS (
        SELECT 
            b.state_abb,
            b.ac_no,
            COALESCE(a.ac_name, CONCAT('AC-', b.ac_no)) AS ac_name,
            b.booth_no,
            b.booth_name,
            b.total_voters,
            b.male_voters,
            b.female_voters,
            b.police_station,
            b.pincode,
            ROW_NUMBER() OVER (PARTITION BY b.state_abb, b.ac_no ORDER BY b.el_booth_id) as rn
        FROM booth_metadata_full_view b
        LEFT JOIN ac_mapping a ON b.state_abb = a.state_abb AND b.ac_no = a.ac_no
    )
    SELECT * FROM ranked_booths WHERE rn <= 2;
    """
    cur.execute(booth_query)
    b_rows = cur.fetchall()
    
    state_booth_voters = {}
    for r in b_rows:
        s_abb, ac_no, ac_name, b_no, b_name, tot_v, m_v, f_v, ps, pin, rn = r
        if s_abb == 'CG':
            s_abb = 'CH'
        if s_abb not in state_booth_voters:
            state_booth_voters[s_abb] = []
        
        tot_v = tot_v or 0
        m_v = m_v or 0
        f_v = f_v or 0
        ratio = round((f_v / max(m_v, 1)) * 1000) if m_v > 0 else 0

        # Requirement 2 Record (DB-ONLY):
        # Age distribution, valid location voter counts, and coordinates are NOT in DB -> set to None ('—')
        state_booth_voters[s_abb].append({
            'state': s_abb,
            'ac_no': ac_no,
            'ac_name': ac_name,
            'booth_no': b_no,
            'booth_name': b_name or f"Booth {b_no}",
            'total_voters': tot_v,
            'voters_with_valid_location': None,  # Not in DB -> '—'
            'age_distribution': None,            # Not in DB -> '—'
            'gender_distribution': {
                'male': m_v,
                'female': f_v,
                'ratio': ratio
            },
            'total_voter_coordinates': None,     # Not in DB -> '—'
            'unique_voter_coordinates': None,    # Not in DB -> '—'
            'valid_voter_coordinates': None,     # Not in DB -> '—'
            'valid_voter_coordinates_pct': None  # Not in DB -> '—'
        })

    # ─── 4. Query Caste Details from RDS ──────────────────────────────────────────
    print("[4/5] Querying Caste Profiles from RDS (caste_details)...")
    caste_query = """
    SELECT state_abb, caste_category, AVG(caste_percentage) AS avg_pct
    FROM caste_details
    WHERE to_be_used = true AND caste_category IS NOT NULL
    GROUP BY state_abb, caste_category
    ORDER BY state_abb, avg_pct DESC;
    """
    try:
        cur.execute(caste_query)
        caste_rows = cur.fetchall()
    except Exception as e:
        print(f"[WARN] Caste query failed: {e}")
        cur.execute('ROLLBACK')
        caste_rows = []

    state_caste_map = {}
    for s_abb, cat, avg_p in caste_rows:
        if s_abb not in state_caste_map:
            state_caste_map[s_abb] = []
        state_caste_map[s_abb].append({
            'category': cat,
            'pct': round(float(avg_p) * 100, 1) if avg_p <= 1.0 else round(float(avg_p), 1)
        })

    # ─── 4b. Query Urban vs Rural Demographics from ac_details ──────────────────
    print("[4b/5] Deriving Urban vs Rural Demographics from RDS (ac_details)...")
    ur_query = """
    SELECT 
        state_abb,
        ROUND(SUM(CASE WHEN ac_region = 'rural' THEN total_electoral_count ELSE 0 END) * 100.0 / NULLIF(SUM(total_electoral_count), 0), 1) as rural_pct,
        ROUND(AVG(CASE WHEN ac_region = 'rural' THEN poll_percentage END)::numeric, 1) as rural_turnout,
        ROUND(SUM(CASE WHEN ac_region = 'urban' THEN total_electoral_count ELSE 0 END) * 100.0 / NULLIF(SUM(total_electoral_count), 0), 1) as urban_pct,
        ROUND(AVG(CASE WHEN ac_region = 'urban' THEN poll_percentage END)::numeric, 1) as urban_turnout,
        ROUND(SUM(CASE WHEN ac_region = 'semi_urban' THEN total_electoral_count ELSE 0 END) * 100.0 / NULLIF(SUM(total_electoral_count), 0), 1) as semi_urban_pct
    FROM ac_details
    WHERE ac_region IS NOT NULL
    GROUP BY state_abb;
    """
    try:
        cur.execute(ur_query)
        ur_rows = cur.fetchall()
    except Exception as e:
        print(f"[WARN] Urban/Rural query failed: {e}")
        cur.execute('ROLLBACK')
        ur_rows = []

    state_ur_map = {}
    for s_abb, r_pct, r_to, u_pct, u_to, su_pct in ur_rows:
        if s_abb == 'CG':
            s_abb = 'CH'
        state_ur_map[s_abb] = {
            'rural_pct': float(r_pct) if r_pct is not None else 0.0,
            'rural_turnout': float(r_to) if r_to is not None else 0.0,
            'urban_pct': float(u_pct) if u_pct is not None else 0.0,
            'urban_turnout': float(u_to) if u_to is not None else 0.0,
            'semi_urban_pct': float(su_pct) if su_pct is not None else 0.0
        }

    # ─── 5. Update state_glance_cache.json ───────────────────────────────────
    print("[5/5] Writing DB-ONLY Booth & Voter data into state_glance_cache.json...")
    cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'data', 'state_glance_cache.json')
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            state_glance = json.load(f)
    except Exception:
        state_glance = {}

    try:
        redis_client = get_redis()
    except Exception:
        redis_client = None

    for s_abb, s_name in STATE_NAMES.items():
        if s_abb not in state_glance:
            state_glance[s_abb] = {}

        zones = state_zone_map.get(s_abb, [])
        acs = state_acs_map.get(s_abb, [])
        booth_details = state_booth_details.get(s_abb, [])
        booth_voters = state_booth_voters.get(s_abb, [])

        existing_booth = state_glance[s_abb].get('booth') or {}
        existing_booth_avail = existing_booth.get('availability_pct', 0.0)

        if zones or booth_details:
            tot_booths = sum(z['total_booths'] for z in zones) if zones else sum(b['extracted_booths'] for b in booth_details)
            tot_voters = sum(z['total_voters'] for z in zones) if zones else sum(b['total_voters'] for b in booth_details)
            tot_male = sum(z['male_voters'] for z in zones) if zones else sum(b['male_voters'] for b in booth_details)
            tot_female = sum(z['female_voters'] for z in zones) if zones else sum(b['female_voters'] for b in booth_details)
            ac_cnt = len(booth_details) if booth_details else len(acs)

            # Field averages weighted by booths from RDS
            if zones:
                blk_avg = round(sum(z['block_pct'] * z['total_booths'] for z in zones) / max(tot_booths, 1), 1)
                pan_avg = round(sum(z['panchayat_pct'] * z['total_booths'] for z in zones) / max(tot_booths, 1), 1)
                ps_avg = round(sum(z['police_stn_pct'] * z['total_booths'] for z in zones) / max(tot_booths, 1), 1)
                pin_avg = round(sum(z['pincode_pct'] * z['total_booths'] for z in zones) / max(tot_booths, 1), 1)
                addr_avg = round(sum(z['address_pct'] * z['total_booths'] for z in zones) / max(tot_booths, 1), 1)
                admin_score = round((blk_avg + pan_avg + ps_avg + pin_avg) / 4.0, 1)
            else:
                blk_avg, pan_avg, ps_avg, pin_avg, addr_avg, admin_score = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

            missing_acs = sorted([a for a in acs if a.get('total_missing', 0) > 0], key=lambda x: x.get('total_missing', 0), reverse=True)[:10]

            valid_voter_acs = [a for a in acs if a.get('total_voters', 0) > 0]
            largest_acs = sorted(valid_voter_acs, key=lambda x: x['total_voters'], reverse=True)[:5]
            smallest_acs = sorted(valid_voter_acs, key=lambda x: x['total_voters'])[:5]

            existing_rev = existing_booth.get('revision_breakdown') or {}

            state_glance[s_abb]['booth'] = {
                'availability_pct': existing_booth_avail or 100.0,
                'total_booths': tot_booths,
                'pre_sir_booths': existing_rev.get('pre_sir') or existing_booth.get('pre_sir_booths', 0),
                'ssr_booths': existing_rev.get('ssr') or existing_booth.get('ssr_booths', 0),
                'sir_booths': existing_rev.get('sir') or existing_booth.get('sir_booths', 0),
                'post_sir_booths': existing_rev.get('post_sir') or existing_booth.get('post_sir_booths', 0),
                'revision_stage': existing_rev.get('primary_stage') or existing_booth.get('revision_stage', '—'),
                'revision_breakdown': existing_rev,
                'unique_coordinates': existing_booth.get('unique_coordinates'),
                'valid_coordinates': existing_booth.get('valid_coordinates'),
                'valid_coordinates_pct': existing_booth.get('valid_coordinates_pct'),
                'geo_validation': existing_booth.get('geo_validation'),
                'map_pins': existing_booth.get('map_pins', []),
                'total_acs': ac_cnt,
                'avg_booths_per_ac': round(tot_booths / max(ac_cnt, 1), 1),
                'admin_quality_score': admin_score,
                'field_completeness': {
                    'block_taluka_pct': blk_avg,
                    'panchayat_pct': pan_avg,
                    'police_station_pct': ps_avg,
                    'pincode_pct': pin_avg,
                    'address_pct': addr_avg
                },
                'zones': zones,
                'missing_alerts': missing_acs,
                'booth_details': booth_details  # Requirement 1 Table
            }

            gender_ratio = round((tot_female / max(tot_male, 1)) * 1000) if tot_male > 0 else 0
            avg_v_per_b = round(tot_voters / max(tot_booths, 1)) if tot_booths > 0 else 0

            state_glance[s_abb]['voter'] = {
                'total_voters': tot_voters,
                'voters_with_valid_loc': None,  # Not in DB -> '—'
                'valid_location_pct': None,     # Not in DB -> '—'
                'male_voters': tot_male,
                'female_voters': tot_female,
                'male_pct': round((tot_male / max(tot_voters, 1)) * 100, 1) if tot_voters > 0 else 0.0,
                'female_pct': round((tot_female / max(tot_voters, 1)) * 100, 1) if tot_voters > 0 else 0.0,
                'gender_ratio': gender_ratio,
                'avg_voters_per_booth': avg_v_per_b,
                'age_distribution': None,       # Not in DB -> '—'
                'surname_caste_mapping': None,  # Not in DB -> empty state
                'urban_rural': state_ur_map.get(s_abb),
                'caste_profile': state_caste_map.get(s_abb, [])[:6],
                'zone_distribution': zones,
                'largest_acs': largest_acs,
                'smallest_acs': smallest_acs,
                'booth_voter_details': booth_voters # Requirement 2 Table
            }
        else:
            # State has NO booth records in booth_metadata_full_view in RDS
            state_glance[s_abb]['booth'] = {
                'availability_pct': existing_booth_avail or 0.0,
                'total_booths': 0,
                'unique_coordinates': None,
                'valid_coordinates': None,
                'valid_coordinates_pct': None,
                'geo_validation': None,
                'total_acs': STATE_AC_COUNTS.get(s_abb, 0),
                'avg_booths_per_ac': 0.0,
                'admin_quality_score': 0.0,
                'field_completeness': {'block_taluka_pct': 0.0, 'panchayat_pct': 0.0, 'police_station_pct': 0.0, 'pincode_pct': 0.0, 'address_pct': 0.0},
                'zones': [],
                'missing_alerts': [],
                'booth_details': []
            }
            state_glance[s_abb]['voter'] = {
                'total_voters': 0,
                'voters_with_valid_loc': None,
                'valid_location_pct': None,
                'male_voters': 0,
                'female_voters': 0,
                'male_pct': 0.0,
                'female_pct': 0.0,
                'gender_ratio': 0,
                'avg_voters_per_booth': 0,
                'age_distribution': None,
                'surname_caste_mapping': None,
                'urban_rural': state_ur_map.get(s_abb),
                'caste_profile': state_caste_map.get(s_abb, [])[:6],
                'zone_distribution': [],
                'largest_acs': [],
                'smallest_acs': [],
                'booth_voter_details': []
            }

        # Sync to Redis if client available
        if redis_client:
            try:
                redis_client.set(f'state_glance:{s_abb}', json.dumps(state_glance[s_abb]))
            except Exception as e:
                pass

    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(state_glance, f, indent=2)

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DB-ONLY Aggregation complete in {round(time.time() - t0, 1)}s!")
    return True

if __name__ == '__main__':
    generate_booth_voter_data()
