# Form 20 Backlog Dashboard — Complete Project Context
### Handover Document for New Developer / Antigravity Instance
> **Last Updated:** July 2026 | **Version:** Production-Live

---

## ⚠️ CRITICAL RULES — READ FIRST

> These rules were set by the project owner and MUST be followed strictly:

1. **DO NOT change anything without explicit approval.** Every change requires the owner's consent.
2. **DO NOT auto-proceed.** Wherever approval is required, STOP and wait for the response.
3. **DO NOT assume.** If something is unclear, ASK.
4. **ALWAYS follow the standard development workflow:** Branch → Tests → PR → CI Green → Owner Approves → Merge → Auto-Deploy.
5. **NEVER push directly to `main`.** All changes go through Pull Requests.
6. **Always write test cases** before or alongside any feature/fix.

---

## 📖 Project Overview

**What is this?**
A full-stack internal analytics dashboard for tracking the collection status of **Form 20** (electoral roll data) across all Indian states, Parliamentary Constituencies (PCs), and Assembly Constituencies (ACs).

**Organisation:** Varahe Analytics  
**Purpose:** Track which Form 20 records have been received, downloaded, extracted, pushed to DB, or are still missing — across different election types (AE, GE, BE) and years.

**Key Pages:**
| Page | URL | Description |
|---|---|---|
| Dashboard | `/` | KPI cards, charts, bottlenecks summary |
| Listing | `/listing` | Filterable table of all records |
| Glance Report | `/glance` | Weekly push report — week-by-week breakdown |
| Retro Export | `/retro` | Export data for retrospective analysis |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        EC2 Instance                          │
│  IP: 13.206.145.98   Region: ap-south-1 (Mumbai)           │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐   ┌───────────────┐  │
│  │   Gunicorn   │    │    Redis     │   │  PostgreSQL   │  │
│  │  (Flask app) │◄──►│  (Cache)    │   │  (Local DB)   │  │
│  │  Port 5050   │    │  Port 6379  │   │  Port 5432    │  │
│  └──────┬───────┘    └──────────────┘   └───────────────┘  │
│         │ systemd: form20-dashboard.service                  │
│  ┌──────▼───────┐                                           │
│  │    Nginx     │  ← Reverse proxy (port 80/443)           │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
         ▲
         │  GitHub Actions (CI + Deploy)
         │
┌────────┴──────────────────────────────┐
│  GitHub Repo                           │
│  mayurdeshpande-de-ka/Project-cleanroom│
│  Branch: main (production)             │
└───────────────────────────────────────┘
```

---

## 🖥️ Tech Stack

### Backend
| Item | Detail |
|---|---|
| Language | Python 3.10+ |
| Framework | Flask 3.0+ |
| WSGI Server | Gunicorn 21.2+ |
| Auth | Google OAuth 2.0 (Authlib) |
| DB Driver | psycopg2-binary (PostgreSQL) |
| Cache | Redis 5.0+ |
| Process Manager | systemd (`form20-dashboard.service`) |

### Frontend (React App — `client/` folder)
| Item | Detail |
|---|---|
| Framework | React 19 + TypeScript |
| Build Tool | Vite 6 |
| Styling | Tailwind CSS v4 |
| Charts | Recharts |
| Icons | Lucide React |
| HTTP Client | Axios |
| Routing | React Router DOM v7 |
| Testing | Vitest + React Testing Library |

### Infrastructure
| Item | Detail |
|---|---|
| Cloud | AWS |
| Compute | EC2 (Amazon Linux 2) |
| Database | PostgreSQL — installed **locally on EC2** (NOT RDS) |
| Cache | Redis — running in Docker on EC2 |
| CI/CD | GitHub Actions |

---

## 📁 Project Structure

```
Form 20 Backlog Dashboard/
│
├── app.py                    ← Main Flask application (2183 lines)
├── glance_routes.py          ← Glance Report API routes (separate blueprint)
├── requirements.txt          ← Python dependencies
├── .env                      ← Environment variables (NOT committed to git)
├── .gitignore                ← Git ignore rules
│
├── static/
│   ├── app.js                ← Main frontend JS (vanilla JS, 2372 lines)
│   ├── style.css             ← Minimal global styles
│   └── favicon.png           ← App favicon
│
├── templates/
│   ├── index.html            ← Main app HTML (Flask renders this)
│   ├── login.html            ← Google OAuth login page
│   ├── country_glance.html   ← Country-level glance report
│   └── _footer.html          ← Shared footer partial
│
├── client/                   ← React frontend app
│   ├── src/
│   │   ├── App.tsx           ← App shell + sidebar navigation
│   │   ├── main.tsx          ← React entry point
│   │   ├── index.css         ← Global styles (Tailwind v4)
│   │   └── pages/
│   │       ├── Dashboard.tsx
│   │       ├── Listing.tsx
│   │       ├── GlanceReport.tsx
│   │       └── RetroExport.tsx
│   ├── tests/
│   │   ├── frontend.test.tsx ← 45 frontend test cases
│   │   └── setup.ts          ← Vitest setup
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.ts        ← Vite + Vitest config
│   ├── tsconfig.json
│   ├── postcss.config.js     ← @tailwindcss/postcss (Tailwind v4)
│   └── tailwind.config.js
│
├── tests/
│   ├── test_backend.py       ← 47 backend test cases (API + DB + auth)
│   └── test_url_persistence.py ← 16 URL state tests
│
├── .github/
│   └── workflows/
│       ├── ci.yml            ← CI: lint + test + frontend build
│       └── deploy.yml        ← Deploy to EC2 on merge to main
│
└── docker-compose.yml        ← Redis container config (used on EC2)
```

---

## 🗄️ Database

### Type: Local PostgreSQL on EC2

The project was **migrated from Turso (SQLite cloud) to local PostgreSQL** installed directly on the EC2 instance.

**Why local PostgreSQL?**
- Free (no external cloud DB cost)
- Data stays on the EC2 box
- Low latency (same machine)
- Full PostgreSQL features

### Connection Details

The database credentials are stored in the `.env` file on EC2 at:
```
/home/ec2-user/Form20-backlog-tracker/.env
```

**Environment Variables (DB):**
```env
# Local PostgreSQL on EC2
LOCAL_DB_HOST=localhost
LOCAL_DB_NAME=local_backlog_db
LOCAL_DB_USER=backlog_user
LOCAL_DB_PASS=<password — see .env on EC2>
LOCAL_DB_PORT=5432
```

**How to connect to DB on EC2:**
```bash
# SSH into EC2 first (see EC2 section below)
# Then:
psql -U backlog_user -d local_backlog_db -h localhost
```

**Main Table: `download_tracking`**
```sql
CREATE TABLE download_tracking (
    id                  SERIAL PRIMARY KEY,
    assembly_constituency TEXT NOT NULL,
    state               TEXT NOT NULL,
    type                TEXT NOT NULL,          -- 'AE', 'GE', 'BE', etc.
    record_key          TEXT UNIQUE NOT NULL,   -- state|pc|ac|type|year
    is_sir_state        INTEGER DEFAULT 0,
    download_status     TEXT DEFAULT 'missing',
    extraction_status   TEXT DEFAULT 'pending',
    db_status           TEXT DEFAULT 'not_in_db',
    overall_status      TEXT DEFAULT 'missing',
    wip                 INTEGER DEFAULT 0,
    assigned_to         TEXT,
    remark              TEXT,
    last_updated        TEXT,
    retro_ready         INTEGER DEFAULT 0,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    manual_override     INTEGER DEFAULT 0
);
```

**Secondary Table: `activity_log`**
```sql
CREATE TABLE activity_log (
    id          SERIAL PRIMARY KEY,
    record_key  TEXT,
    action      TEXT,
    old_value   TEXT,
    new_value   TEXT,
    changed_by  TEXT,
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### AWS RDS (Secondary — Analytics only)
There is also an **AWS RDS PostgreSQL** instance used for analytics data (not the main tracker DB).

```env
# AWS RDS (analytics DB — read-only queries from dashboard)
DB_HOST=<rds-endpoint>.ap-south-1.rds.amazonaws.com
DB_PORT=5432
DB_USER=<rds-username>
DB_PASSWORD=<rds-password>
DB_NAME=<database-name>
```
> ⚠️ These credentials are in the `.env` file on EC2. Never commit them to git.

**How the app uses both DBs:**
- `get_db()` → connects to **local PostgreSQL** (main tracker data)
- `get_rds_db()` → connects to **AWS RDS** (analytics/dashboard stats)

---

## 🔐 Credentials & Secrets

### Where are credentials stored?

| Credential | Where |
|---|---|
| DB passwords | `.env` file on EC2 at `/home/ec2-user/Form20-backlog-tracker/.env` |
| Google OAuth secrets | `.env` file on EC2 + GitHub Actions Secrets |
| EC2 SSH key | GitHub Actions Secret: `EC2_SSH_KEY` |
| Flask secret key | `.env` file on EC2 |

### `.env` file structure (on EC2 and local dev)
```env
# Flask
FLASK_SECRET_KEY=<long-random-string>

# Google OAuth
GOOGLE_CLIENT_ID=<your-google-client-id>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<your-google-client-secret>

# Local PostgreSQL on EC2
LOCAL_DB_HOST=localhost
LOCAL_DB_NAME=local_backlog_db
LOCAL_DB_USER=backlog_user
LOCAL_DB_PASS=<password>
LOCAL_DB_PORT=5432

# AWS RDS (analytics)
DB_HOST=<rds-endpoint>.rds.amazonaws.com
DB_PORT=5432
DB_USER=<user>
DB_PASSWORD=<password>
DB_NAME=<dbname>

# Redis (cache)
REDIS_URL=redis://127.0.0.1:6379/0

# Auth toggle (set to 1 for local dev only)
# DISABLE_AUTH=1
```

> ⚠️ `.env` is in `.gitignore`. It is NEVER committed to git. Treat it as top-secret.

### GitHub Actions Secrets
These must be set in GitHub repo → Settings → Secrets and Variables → Actions:

| Secret Name | Value |
|---|---|
| `EC2_SSH_KEY` | Full content of EC2 `.pem` private key file |

---

## ☁️ EC2 Setup

### Instance Details
| Property | Value |
|---|---|
| **Public IP** | `13.206.145.98` |
| **Region** | `ap-south-1` (Mumbai) |
| **OS** | Amazon Linux 2 |
| **User** | `ec2-user` |
| **App directory** | `/home/ec2-user/Form20-backlog-tracker/` |

### How to SSH into EC2
```bash
ssh -i /path/to/your-key.pem ec2-user@13.206.145.98
```
> The `.pem` key file is held securely by the project owner (Mayur Deshpande).

### How the App Runs on EC2

The app is managed by **systemd**:
```bash
# Check service status
sudo systemctl status form20-dashboard.service

# Restart the service
sudo systemctl restart form20-dashboard.service

# View live logs
sudo journalctl -u form20-dashboard.service -f
```

**Service config** (`/etc/systemd/system/form20-dashboard.service`):
```ini
[Unit]
Description=Form 20 Dashboard (Gunicorn)
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/home/ec2-user/Form20-backlog-tracker
EnvironmentFile=/home/ec2-user/Form20-backlog-tracker/.env
ExecStart=/home/ec2-user/Form20-backlog-tracker/venv/bin/gunicorn \
    --workers 2 --bind 0.0.0.0:5050 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

### Redis on EC2
Redis runs as a Docker container:
```bash
# Start Redis
docker-compose up -d redis

# Check Redis
docker ps | grep redis
```

### PostgreSQL on EC2
```bash
# Check PostgreSQL service
sudo systemctl status postgresql

# Connect to DB
psql -U backlog_user -d local_backlog_db -h localhost

# List tables
\dt

# Quit
\q
```

---

## 🔗 GitHub Repository

| Property | Value |
|---|---|
| **Repo URL** | https://github.com/mayurdeshpande-de-ka/Project-cleanroom |
| **Main Branch** | `main` (production) |
| **Owner** | mayurdeshpande-de-ka |

### Branch Naming Convention
| Type | Format | Example |
|---|---|---|
| New Feature | `feature/<name>` | `feature/retro-export-filter` |
| Bug Fix | `fix/<name>` | `fix/stats-count-mismatch` |
| Urgent Fix | `hotfix/<name>` | `hotfix/login-broken` |
| Testing | `test/<name>` | `test/add-glance-tests` |

### Commit Message Convention
| Type | Prefix | Example |
|---|---|---|
| New feature | `feat:` | `feat: Add state filter to listing` |
| Bug fix | `fix:` | `fix: Correct wip_count calculation` |
| Tests | `test:` | `test: Add Dashboard component tests` |
| CI/CD | `ci:` | `ci: Add frontend test step` |
| Docs | `docs:` | `docs: Update README` |

---

## 🔄 CI/CD Pipeline

### Rule: NOTHING goes to production directly. Ever.

```
Write Code + Tests
      │
      ▼
git checkout -b feature/<name>
git commit -m "feat: ..."
git push origin feature/<name>
      │
      ▼
Open Pull Request on GitHub
      │
      ▼
GitHub Actions CI runs automatically:
  ✅ backend-lint-test (flake8 + pytest)
  ✅ frontend-build (npm ci + npm test + npm run build)
      │
      ▼
Owner reviews and approves PR
      │  (wait for approval — do NOT auto-merge)
      ▼
Merge PR → main
      │
      ▼
deploy.yml triggers:
  → rsync code to EC2
  → pip install -r requirements.txt
  → sudo systemctl restart form20-dashboard.service
      │
      ▼
🚀 Live on http://13.206.145.98
```

### CI Workflow (`.github/workflows/ci.yml`)
Runs on every PR and push to `main`:
1. **backend-lint-test**: Python 3.10 → pip install → flake8 lint → pytest
2. **frontend-build**: Node 20 → npm ci → npm test (Vitest) → npm run build (Vite)

### Deploy Workflow (`.github/workflows/deploy.yml`)
Runs on push to `main` (after CI passes):
1. Rsync all code to EC2 (excludes: venv, .git, *.db, *.csv, *.log)
2. SSH into EC2, activate venv, pip install, restart systemd service

---

## 🧪 Testing

### Backend Tests
```bash
# Run all backend tests
pytest tests/test_backend.py tests/test_url_persistence.py -v

# Run with DISABLE_AUTH for local testing
DISABLE_AUTH=1 pytest tests/ -v
```

**Test files:**
| File | Tests | Coverage |
|---|---|---|
| `tests/test_backend.py` | 47 tests | DB CRUD, API routes, business logic, auth guards |
| `tests/test_url_persistence.py` | 16 tests | URL hash state persistence feature |

### Frontend Tests
```bash
cd client

# Run tests once
npm test

# Watch mode
npm run test:watch

# With coverage report
npm run test:coverage
```

**Test file:** `client/tests/frontend.test.tsx` — 45 tests covering:
- Navigation & App Shell
- Dashboard Component (loading, data display, error states)
- Listing Component (filters, search, pagination, badges)
- GlanceReport Component (toggle, filters, empty state)
- Status Badge rendering
- Accessibility (headings, placeholders, keyboard)

---

## 💻 Local Development Setup

### Prerequisites
- Python 3.10+
- Node.js 20+
- Git

### Backend Setup
```bash
# Clone repo
git clone https://github.com/mayurdeshpande-de-ka/Project-cleanroom.git
cd Project-cleanroom

# Create virtual environment
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate
# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file (copy from template above, fill in credentials)
# Set DISABLE_AUTH=1 for local dev (skips Google OAuth)

# Run Flask app
python app.py
# App runs on http://127.0.0.1:5050
```

### Frontend Setup
```bash
cd client

# Install dependencies
npm install

# Run dev server (proxies /api to Flask on :5050)
npm run dev
# Frontend runs on http://localhost:5173

# Build for production
npm run build

# Run tests
npm test
```

### ⚠️ Important Notes for Local Dev
1. Set `DISABLE_AUTH=1` in your `.env` — otherwise Google OAuth blocks all pages
2. The React dev server proxies `/api/*` to `http://127.0.0.1:5050` (Flask must be running)
3. DB credentials in `.env` are required — contact project owner for local dev credentials
4. `*.json`, `*.db`, `*.csv` files are gitignored — data files are NOT in the repo

---

## 🔐 Google OAuth Setup

The app uses Google OAuth 2.0 for authentication. Only **@varaheanalytics.com** email domain is allowed.

**Required Google Cloud Console settings:**
- Project: Varahe Analytics
- OAuth 2.0 Client ID configured with:
  - Authorised redirect URIs: `http://13.206.145.98/auth/callback`
  - (Add `http://localhost:5050/auth/callback` for local dev)

**Domain restriction** is enforced in `app.py`:
```python
if not email.endswith('@varaheanalytics.com'):
    return "Access denied", 403
```

---

## 📊 Key API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/stats` | Dashboard KPIs and charts data |
| GET | `/api/records` | Paginated, filterable record list |
| PATCH | `/api/records/<id>` | Update a record's status |
| GET | `/api/glance_report` | Weekly push glance data |
| GET | `/api/filters` | Available filter options |
| GET | `/api/retro_export` | Retro export data |
| GET | `/login` | Google OAuth login page |
| GET | `/auth/callback` | OAuth callback (handled by Authlib) |
| GET | `/logout` | Clear session |

---

## 📜 Development Rules (Golden Rules)

These rules are strictly enforced by the project owner:

### The 6 Commandments

1. **Branch for everything** — Never work directly on `main`
2. **Test before PR** — Write tests alongside code, not after deployment
3. **CI must be green** — PR cannot be merged if any CI check fails
4. **Owner approves merge** — Agent/developer STOPS after CI green and waits
5. **Auto-deploy on merge** — Once merged, EC2 deploys automatically; no manual deploys
6. **No assumptions** — If uncertain, ASK. Do not guess and proceed.

### PR Checklist (before requesting approval)
- [ ] Feature works locally
- [ ] Test cases written and passing (`pytest` + `npm test`)
- [ ] CI checks green on GitHub
- [ ] No sensitive data (passwords, keys) in commits
- [ ] Commit messages follow convention (`feat:`, `fix:`, etc.)

---

## 🗓️ Completed Features (History)

| Feature | Branch | Status |
|---|---|---|
| Initial Flask dashboard | `main` | ✅ Live |
| React frontend (Vite + TS) | `main` | ✅ Live |
| Google OAuth authentication | `main` | ✅ Live |
| Turso → Local PostgreSQL migration | `feature/postgres-tests` | ✅ Merged |
| Backend test suite (47 tests) | `feature/postgres-tests` | ✅ Merged |
| Frontend test suite (45 tests) | `feature/postgres-tests` | ✅ Merged |
| URL state persistence on refresh | `feature/url-state-persistence` | ✅ Merged + Live |

---

## 🚨 Known Issues & Watchpoints

1. **`client/tsconfig.json` is in `.gitignore` (`*.json`)** — if it disappears, recreate it. The content is in `vite.config.ts`.
2. **Data files not in git** — `*.json`, `*.db`, `*.csv` are gitignored. They live only on EC2.
3. **Redis must be running** — If Redis is down, the dashboard cache degrades to in-memory (single-worker only). Start with `docker-compose up -d redis`.
4. **Google OAuth domain restriction** — Only `@varaheanalytics.com` emails can log in. Change in `app.py` if needed for college use.
5. **Gunicorn workers = 2** — Set in systemd service file. Increase if load requires.
6. **`libsql-client` still in requirements.txt** — Legacy Turso dependency. Safe to keep or remove.

---

## 📞 Contact / Ownership

| Role | Name |
|---|---|
| Project Owner | Mayur Deshpande (mayurdeshpande-de-ka) |
| Organisation | Varahe Analytics |
| GitHub | https://github.com/mayurdeshpande-de-ka |

> For EC2 SSH key access, PostgreSQL credentials, RDS credentials, and Google OAuth secrets — contact the project owner directly. These are NOT stored in the repository.

---

## 🤖 Instructions for Antigravity (AI Agent)

If you are another Antigravity instance picking up this project:

1. **Read this file fully before doing anything**
2. **Read the CRITICAL RULES at the top again**
3. Always check `git log --oneline -10` to understand recent history
4. Always check `gh pr list` to see open PRs
5. Always check `gh run list --branch main --limit 5` to see recent CI/deploy status
6. Before any change: create a branch, never touch `main` directly
7. Before merging: confirm with the owner even if CI is green
8. Use `DISABLE_AUTH=1` for any local testing

**Quick status check commands:**
```bash
# See recent deployments
gh run list --branch main --limit 5

# See open PRs
gh pr list

# Check EC2 app status (requires SSH access)
ssh -i key.pem ec2-user@13.206.145.98 "sudo systemctl status form20-dashboard.service"

# Run all local tests
DISABLE_AUTH=1 pytest tests/ -v && cd client && npm test
```
