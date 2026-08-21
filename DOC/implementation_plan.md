# Replace Turso DB with Local PostgreSQL on EC2

This plan outlines the steps to replace the external Turso (SQLite Edge) database with a locally installed PostgreSQL database directly on your EC2 instance. 

## User Review Required
> [!WARNING]
> Replacing Turso with local PostgreSQL requires changing the SQL syntax in your application (SQLite uses `?` for variables, while psycopg2 uses `%s`). I will need to update several files (`app_fixed.py` / `app.py`) to accommodate this.
> Also, since I am operating from your local Windows machine, **you** will need to run a few installation commands directly on the EC2 terminal (SSH) to install PostgreSQL, as I do not have your SSH keys to do it automatically.

## Open Questions
1. You already have a large AWS RDS Postgres database connected. Are you sure you want to install a **second** separate PostgreSQL instance locally on the EC2 server, rather than just adding these small Turso tables (`download_tracking` and `activity_log`) into your existing AWS RDS database? (Putting them in RDS would be much easier and require no installation on EC2). Please confirm which route you prefer.

## Proposed Changes

### EC2 Environment Setup (Manual steps required by you)
I will provide a script containing the exact commands to run on your EC2 instance to:
- Install PostgreSQL (`sudo dnf install postgresql15-server` or similar depending on OS).
- Initialize and start the PostgreSQL service.
- Create a new database `local_backlog_db` and user.

### Data Migration
- **Script**: Create `migrate_turso_to_local_pg.py`
- Connects to your Turso DB via the existing credentials.
- Extracts all data from `download_tracking` and `activity_log` tables.
- Inserts this data into the new local PostgreSQL database.

### Codebase Modification
- **[MODIFY]** `app_fixed.py` (and `app.py` if applicable):
  - Rewrite `get_db()` function to use `psycopg2` connecting to `localhost:5432` instead of `libsql_client`.
  - Hunt down all `.execute()` calls that hit the Turso DB and update the parameter binding syntax from SQLite (`?`) to PostgreSQL (`%s`).
  - Update `INSERT` statements that rely on `AUTOINCREMENT` to use Postgres `RETURNING id` semantics if needed.
- **[MODIFY]** `.env`
  - Add `LOCAL_DB_USER`, `LOCAL_DB_PASS`, `LOCAL_DB_NAME` variables.

## Verification Plan
### Automated Tests
- Run the migration script locally to verify schema compatibility.
- Ensure the CI workflow still passes.

### Manual Verification
- You will need to SSH into EC2, run the provided PostgreSQL setup script, run the migration script, and restart the backend service. We will then verify the dashboard continues to function correctly without Turso.

