# Form 20 Dashboard - Deployment Handover

This document outlines the complete environment setup, runbooks, and EC2 commands required for a new developer or DevOps engineer to take over deployment and maintenance of this application.

---

## 1. Local Development Setup

**Prerequisites:** Python 3.9+, Git.

1. **Clone & Virtual Environment:**
   ```bash
   git clone <repo_url>
   cd "Form 20 Backlog Dashboard"
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Environment Variables (`.env`):**
   Ensure `.env` exists in the root directory. Required keys:
   ```env
   DB_HOST=your-rds-endpoint.amazonaws.com
   DB_PORT=5432
   DB_USER=your_db_user
   DB_PASSWORD=your_db_password
   DB_NAME=your_db_name
   GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your_client_secret
   SECRET_KEY=flask_session_secret
   ```
4. **Run Locally:**
   ```bash
   python app.py
   ```
   *Note: Ensure `debug=True` and `use_reloader=True` are set in `app.py` for local dev if you want templates to auto-reload.*

---

## 2. EC2 Production Deployment

The application is deployed on an AWS EC2 instance (Ubuntu/Debian or Amazon Linux). 

### 2.1 Server Provisioning Script
A shell script (`setup_ec2_environment.sh`) is provided to automate the underlying dependencies.
```bash
chmod +x setup_ec2_environment.sh
./setup_ec2_environment.sh
```
**What this script does:**
1. Installs Redis, Python3, and pip.
2. Enables and starts the `redis-server` systemctl service.
3. Installs Python packages (`psycopg2-binary`, `flask`, `gunicorn`, `redis`).
4. Configures a midnight Cron Job to automatically run `cron_daily_state_glance.py`.

### 2.2 Starting the App via Gunicorn (Production)
Do not use `python app.py` for production. Use Gunicorn as the WSGI HTTP Server.
```bash
gunicorn --workers 4 --bind 0.0.0.0:5050 app:app --daemon
```

### 2.3 Setting up systemd (Recommended for Auto-Restart)
Create a service file to ensure the app stays alive:
```bash
sudo nano /etc/systemd/system/form20dash.service
```
**Content:**
```ini
[Unit]
Description=Gunicorn instance to serve Form 20 Dashboard
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/Form-20-Backlog-Dashboard
Environment="PATH=/home/ubuntu/Form-20-Backlog-Dashboard/venv/bin"
ExecStart=/home/ubuntu/Form-20-Backlog-Dashboard/venv/bin/gunicorn --workers 4 --bind 0.0.0.0:5050 app:app

[Install]
WantedBy=multi-user.target
```
**Enable and Start:**
```bash
sudo systemctl daemon-reload
sudo systemctl start form20dash
sudo systemctl enable form20dash
```

---

## 3. Data Pipeline & Cron Operations

The dashboard relies on nightly aggregation dumps (JSON/GeoJSON) generated from the massive RDS database. If the dashboard is showing outdated data, the cron job might have failed.

**To manually trigger the ETL pipeline:**
```bash
python cron_daily_state_glance.py
```
This updates everything inside the `static/data/` folder (e.g., `state_glance_cache.json`, `country_glance.json`).

**To verify the Cron Job:**
```bash
crontab -l
# Expected output: 0 0 * * * /usr/bin/python3 /path/to/cron_daily_state_glance.py >> /path/to/cron_nightly.log 2>&1
```
Check the cron log if there are failures:
```bash
cat cron_nightly.log
```

---

## 4. Troubleshooting Handover Guide

* **Dashboard charts are blank or 404ing:** The JSON payload in `static/data/` is missing. Run `cron_daily_state_glance.py` to regenerate them.
* **OAuth Login Fails / Redirect URI mismatch:** Ensure the IP address or Domain Name of your EC2 instance is whitelisted in the Google Cloud Console under Authorized Redirect URIs.
* **UI Changes not reflecting:** Flask caches Jinja templates heavily in production. If you edit an `.html` file in `templates/`, you **must restart Gunicorn**:
  ```bash
  sudo systemctl restart form20dash
  ```
* **Map boundaries missing:** Check that `district_data_dump.json` is intact. The Leaflet maps rely purely on local GeoJSON to prevent browser freezing.
