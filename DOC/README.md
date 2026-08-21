# Form 20 Backlog Dashboard

## Project State & Handover

This project is a Flask-based internal dashboard for tracking Form 20 election data for a political consultancy. The user interface has been completely transitioned from its initial state into a custom, highly-polished Tailwind CSS "Dense View" design that mirrors modern enterprise operations dashboards.

### Recent Updates (Current Progress)
- **Retro Export Feature:** Implemented a new `/api/retro/export` backend endpoint in `app.py` that reads, filters, and streams data directly from the large `RETRO.csv` file. It supports downloading as both CSV and Excel (`.xlsx`).
- **Retro Export Modal:** Added a cleanly designed frontend modal (accessible via "Retro Export" in the top navbar). The dropdowns dynamically populate with exact, valid filter options from the database.
- **Tailwind UI Integration:** All styles are completely driven by the custom Tailwind configuration script located in the `<head>` of `index.html`. The old `style.css` is intentionally empty.

### Architecture Overview
- **Backend (`app.py`):** A Flask server (running on `http://127.0.0.1:5050`). Uses a local SQLite database (`data.db`) for tracking operational status (missing, downloaded, extracted, completed, pending).
- **Frontend (`index.html` & `app.js`):** A pure HTML/JS frontend. `app.js` handles data fetching (`/api/records`, `/api/stats`, `/api/filters`) and dynamic DOM manipulation to build out the dashboard table and filter panels.
- **Data Initialization (`init_db.py`):** Script to load initial tracking data from an Excel tracker.

### ⚠️ Critical Environment Quirks (For the Next Agent)
- **Background Terminal Glitch:** The AI Agent's integrated terminal/PowerShell environment currently lacks permissions to execute commands natively on the user's `D:\` drive or spawn `python.exe` processes (`Access is denied` / `DriveNotFoundException`). 
- **Action Required:** Do **NOT** attempt to use the `run_command` or background tasks to start the Flask server. It will fail. Instead, you must instruct the user to run `python app.py` manually from their own command prompt to view and test your changes.

### Remaining To-Dos (Next Steps)
- **Edit & Assignment Features:** Implement the remaining UI interactions (like the Edit Modal and Bulk Assignment logic) and wire them up to the backend using the new Tailwind structure.
- **Testing & Review:** Verify API reliability for all new download routes and ensure consistent filtering logic.
