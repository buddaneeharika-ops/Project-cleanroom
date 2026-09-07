import json
from flask import jsonify, render_template, request
from app import app, get_rds_db, cache_get, STATE_AC_COUNTS, STATE_NAMES

# ─── State abbreviation → full name mapping (for GeoJSON matching) ───────────
STATE_ABB_TO_NAME = {v: k for k, v in {k: v for k, v in STATE_NAMES.items()}.items()}

OTHER_QUERIES = {
    "LGD": """
        SELECT ld.state_abb, COUNT(DISTINCT ld.district_code) AS district_count
        FROM lgd_directory ld GROUP BY ld.state_abb
    """,
    "Ejalshakti": """
        SELECT ld.state_abb, COUNT(DISTINCT ep.village_name) AS village_count
        FROM ejalshakti_portal ep
        LEFT JOIN lgd_directory ld ON ld.lgd_code = ep.lgd_code
        GROUP BY ld.state_abb
    """,
    "Joshua": """
        SELECT jp.state_abb, COUNT(DISTINCT jp.district_name) AS JOSHUA_district_count
        FROM joshua_population jp GROUP BY jp.state_abb
    """,
    "KYS": """
        SELECT sl.state_abb, COUNT(DISTINCT sl.district_name) AS KYS_distinct_count
        FROM school_locator sl GROUP BY sl.state_abb
    """,
    "Muslim Census": """
        SELECT mc.state_abb, COUNT(DISTINCT mc.district_name) AS MUSLIM_district_count
        FROM muslim_census mc GROUP BY mc.state_abb
    """,
    "SECC": """
        SELECT sa.state_abb, COUNT(DISTINCT sa.lgd_code) AS SECC_lgd_code_count
        FROM secc_abstract sa GROUP BY sa.state_abb
    """
}


def get_other_sources_data(force_refresh=False):
    """Queries RDS for the other tables and returns state-level mappings."""
    if not force_refresh:
        cached = cache_get('other_sources')
        if cached is not None:
            return cached

    conn = get_rds_db()
    if not conn:
        return {}

    results = {
        "LGD": {}, "Ejalshakti": {}, "Joshua": {},
        "KYS": {}, "Muslim Census": {}, "SECC": {}
    }

    try:
        cur = conn.cursor()
        for name, query in OTHER_QUERIES.items():
            try:
                cur.execute(query)
                rows = cur.fetchall()
                for row in rows:
                    state_abb = row[0]
                    count = row[1]
                    results[name][state_abb] = count
            except Exception as e:
                results[name] = "error"
                cur.execute('ROLLBACK')
    except Exception as e:
        pass
    finally:
        conn.close()

    cache_set('other_sources', results)
    return results


from app import cache_set

@app.route('/api/country_glance/data', endpoint='api_country_glance_data')
def api_country_glance():
    """State-level coverage matrix for all 10 metrics."""
    analytics = cache_get('analytics') or {}

    form20_prog = {item['state']: item['pct'] for item in analytics.get('form20', {}).get('state_progress', [])}
    retro_prog  = {item['state']: item['pct'] for item in analytics.get('retro', {}).get('state_progress', [])}
    caste_prog  = {item['state']: item['pct'] for item in analytics.get('caste', {}).get('state_progress', [])}
    booth_prog  = {item['state']: item['pct'] for item in analytics.get('booth', {}).get('state_progress', [])}

    other_sources = get_other_sources_data()

    matrix = []
    for state_abb, state_name in STATE_NAMES.items():
        row = {
            "state_name": state_name,
            "state_abb":  state_abb,
            "retro":  retro_prog.get(state_abb, 0),
            "form20": form20_prog.get(state_abb, 0),
            "caste":  caste_prog.get(state_abb, 0),
            "booth":  booth_prog.get(state_abb, 0),
            "muslim": 100 if other_sources.get("Muslim Census") != "error" and other_sources.get("Muslim Census", {}).get(state_abb, 0) > 0 else (0 if other_sources.get("Muslim Census") != "error" else -1),
            "joshua": 100 if other_sources.get("Joshua") != "error"        and other_sources.get("Joshua", {}).get(state_abb, 0) > 0        else (0 if other_sources.get("Joshua") != "error" else -1),
            "kys":    100 if other_sources.get("KYS") != "error"           and other_sources.get("KYS", {}).get(state_abb, 0) > 0           else (0 if other_sources.get("KYS") != "error" else -1),
            "lgd":    100 if other_sources.get("LGD") != "error"           and other_sources.get("LGD", {}).get(state_abb, 0) > 0           else (0 if other_sources.get("LGD") != "error" else -1),
            "ejal":   100 if other_sources.get("Ejalshakti") != "error"    and other_sources.get("Ejalshakti", {}).get(state_abb, 0) > 0    else (0 if other_sources.get("Ejalshakti") != "error" else -1),
            "secc":   100 if other_sources.get("SECC") != "error"          and other_sources.get("SECC", {}).get(state_abb, 0) > 0          else (0 if other_sources.get("SECC") != "error" else -1),
        }
        matrix.append(row)

    return jsonify({
        "success": True,
        "national_avg": {
            "retro":  analytics.get('retro',  {}).get('coverage_pct_all', 0),
            "form20": analytics.get('form20', {}).get('coverage_pct_all', 0),
            "caste":  analytics.get('caste',  {}).get('coverage_pct_all', 0),
            "booth":  analytics.get('booth',  {}).get('coverage_pct_all', 0),
        },
        "matrix": sorted(matrix, key=lambda x: x['state_name'])
    })



