# Project Content Context (For AI Chat Handover)

## Project Overview
**Form 20 Backlog Dashboard** is a comprehensive Python/Flask web application designed to monitor and visualize data engineering efforts, polling booth mapping, and demographic coverage across India. 

The application heavily relies on pre-aggregated data (JSON and GeoJSON) rendered on a beautiful, modern Tailwind CSS + Chart.js + Leaflet mapping frontend.

## Architecture & Technology Stack
* **Backend:** Flask (Python 3)
* **Database:** SQLite (`data.db`, `dashboard.db`) syncing dynamically from an upstream PostgreSQL RDS.
* **Frontend:** HTML/CSS (Jinja2 Templates), Tailwind CSS (via CDN), Vanilla JavaScript, Chart.js, Leaflet.js.
* **Data Processing:** Pandas, NumPy, psycopg2.
* **Authentication:** Google OAuth 2.0 (`@login_required`).

## File Structure & Entry Points
* **`app.py`**: The main Flask application server. Contains auth logic, API endpoints, and template rendering.
* **`glance_routes.py`**: Handles auxiliary API routes for dashboard data.
* **`generate_glance_data.py` & `generate_country_glance.py`**: ETL scripts that query the Postgres database and dump static JSON metrics to `static/data/`.
* **`cron_daily_state_glance.py`**: The cron wrapper that orchestrates the nightly ETL dumps.
* **`setup_ec2_environment.sh` / `setup_windows_cron.ps1`**: OS-specific scripts for deploying the environment and crontabs.

## Current State of Development
* The frontend has been massively optimized. The UI has been stripped of unnecessary cruft, unused scripts were purged, and modern interactive elements were injected.
* **Kerala (KL) Specific Feature:** We recently implemented a *Polling Booth Proximity Analysis* graph for Kerala (`KL`), reading from Excel data and converting it to Chart.js via JSON extraction.
* The system is designed to gracefully fallback to pre-rendered `JSON` caches if the upstream database goes down or times out.

## AI Instructions for New Session
When taking over this context:
1. Review `DASHBOARD_DOCUMENTATION.md` for exact formulas, variables, and API contracts.
2. Review `Handover.md` for deployment context.
3. Be aware that changes to data aggregation logic should be made in the `generate_*.py` scripts, while changes to the UI belong in the `templates/` folder.
