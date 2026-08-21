# Form 20 Backlog Dashboard - Technical & API Documentation

## 1. Application Pages & Routes
* **`/`** - Index page. Serves the Form 20 backlog tracker.
* **`/country-glance-report`** - The National macro-level dashboard. Loads the entire country's aggregated coverage.
* **`/state-glance-report`** - The state-level drill-down dashboard. Requires `?state_abb=` URL parameter to persist state.
* **`/indexing-visualizer`** - Shows indexing progress and data engineering statistics.
* **`/login_page` & `/auth/callback`** - Google OAuth 2.0 flow.

---

## 2. API Endpoints

### 2.1 State Glance API
* **Endpoint:** `/api/state_glance/data`
* **Method:** `GET`
* **Parameters:** `state_abb` (e.g., `KL`, `BR`)
* **Behavior:** Checks local JSON cache `static/data/state_glance_cache.json`. If missing or running dynamically, queries the backend. Returns a heavily nested JSON containing:
  * `hero`: Top-level aggregated percentages.
  * `retro`: Matrix of General/Assembly elections availability.
  * `form20`: Quality remarks, missing data tables.
  * `demographics`: JOSHUA, Muslim Census data.
  * `overview`: LGD, SECC, eJal Shakti, and mapped JSON polygons.

### 2.2 Country Glance API
* **Endpoint:** `/api/country_glance/data`
* **Method:** `GET`
* **Behavior:** Loads the `static/data/country_glance.json` artifact (generated nightly). Serves pan-India metrics, top/bottom performing states, and geographical JSON arrays for the macro-choropleth map.

### 2.3 Synchronization & Admin APIs
* **`/api/sync-rds` (POST):** Triggers `robust_sync.py` to fetch from the Postgres RDS and update the local SQLite database.
* **`/api/records` (GET/PATCH):** CRUD endpoints for the backlog tracker UI.
* **`/api/export` (POST):** Exports filtered tracker data to Excel.
* **`/api/retro/count` (GET):** Fetches dynamic Retro data counts per AC.

---

## 3. Data Points, Variables & Formulas

### 3.1 Hero Metrics (Form 20 & Retro Coverage)
* **`Expected Form 20 ACs`**: A fixed constant dictionary `STATE_AC_COUNTS`. (e.g., `KL` = 140, `UP` = 403).
* **`Available Form 20 ACs`**: `COUNT(DISTINCT ac_no)` where `state_abb = X` and `pdf_availability = 'Yes'`.
* **Formula:** `(Available Form 20 / Expected Form 20) * 100`

### 3.2 Retro Availability Formulas
* **`Expected Retro Elections`**: Extracted from `ac_election_mapping` table for `el_type NOT LIKE '%BP%'` (No by-polls).
* **`Available Retro Elections`**: Matched records in the `retro_data` mapping.
* **Formula:** `(Available Retro / Expected Retro) * 100`. Split visually in the UI into a 4-quadrant matrix (AE, GE, AE-BP, GE-BP).

### 3.3 Demographic Aggregations
* **JOSHUA Data**: Sum of `population`, `hindu_pop`, `muslim_pop`, etc. grouped by State.
* **Muslim Census Data**: `SUM(muslim_pop) / SUM(total_pop) * 100` mapped down to the district/sub-district level.

### 3.4 LGD / SECC / eJal Shakti Match Rates
* **`LGD Total Villages`**: Total row count per state in `lgd_directory`.
* **`SECC Match Count`**: Count of LGD villages that have a corresponding SECC record.
* **Formula (Coverage):** `(SECC Matched / LGD Total) * 100`
* **EJal Shakti Coverage**: `SUM(households_with_tap) / SUM(total_households) * 100`.

### 3.5 Kerala Polling Booth Proximity (KL Only)
* **Data Source:** `KL/KL-Booth avg distance & Valid_invalid.xlsx` -> `kl_insights.json`
* **`Valid Geocodes`**: Booths where `lat_long_validity == 'Valid'` and distance > 0.
* **`ECI Mandate Compliant (≤ 2km)`**: `COUNT(booths) WHERE avg_distance_km <= 2.0`.
* **Formula:** `(Compliant Booths / Total Valid Booths) * 100` (Currently 59.1% for Kerala).

---

## 4. Key SQL Queries

**4.1 Base State Retro Query:**
```sql
SELECT state_abb, COUNT(DISTINCT (el_year, el_type, ac_no)) 
FROM ac_election_mapping 
WHERE el_type NOT LIKE '%BP%' 
GROUP BY state_abb;
```

**4.2 Form 20 Availability Query:**
```sql
SELECT state_name, COUNT(DISTINCT ac_name) 
FROM local_form20 
WHERE pdf_availability = 'Yes' 
GROUP BY state_name;
```

**4.3 eJal Shakti Aggregation:**
```sql
SELECT state_name, 
       SUM(total_pop), 
       SUM(total_households), 
       SUM(households_with_tap) 
FROM ejal_data 
GROUP BY state_name;
```
