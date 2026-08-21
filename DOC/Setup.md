# Project Setup & Configuration Guide

> **IMPORTANT PATH & LOCATION NOTE:** 
> Please ensure that the working directory and any absolute paths inside the `.env` or configurations are correctly updated to match the location of this folder on your laptop. Always execute the backend scripts or Node commands from their respective root directories.

## Overview
This is the **Form 20 Backlog Dashboard** repository. It contains a Python Flask backend and a React (Vite + TypeScript) frontend. 

## Requirements
- **Python 3.10+** (For the Flask backend)
- **Node.js 18+** (For the React frontend)
- **Redis** (Optional/Recommended for caching, can be run via Docker)
- A `.env` file containing valid environment variables (already included in this ZIP, but verify if paths need adjustments).

## Backend Setup
1. Open a terminal in the root directory of this extracted folder.
2. Create and activate a Python virtual environment (optional but recommended):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
3. Install the Python dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Verify your local SQLite database (`data.db`) is present.
5. Start the Flask server:
   ```powershell
   python app.py
   ```
   *The backend will typically run on `http://127.0.0.1:5050`.*

## Frontend Setup
1. Open a separate terminal and navigate into the `client/` folder:
   ```powershell
   cd client
   ```
2. Install the Node dependencies:
   ```powershell
   npm install
   ```
3. Start the Vite development server:
   ```powershell
   npm run dev
   ```
   *The frontend will typically run on `http://localhost:5173`.*

## Important Context for New Chats / AI Agents
- **Do not assume the absolute path.** The project location might be `C:\Work\...` on one machine and `D:\Projects\...` on another. Use relative paths (`./`) or dynamically resolve paths using `os.path.dirname(__file__)` in Python.
- **Background Terminal Limitations:** AI integrated terminals may lack permissions to run the Flask server or Vite dev server indefinitely in the background on Windows. You may need to ask the human user to run `python app.py` and `npm run dev` in their own Command Prompt/PowerShell windows.
- Please read `PROJECT_CONTEXT.md` for the full architecture, database structure, and strictly enforced development rules (like PR workflows).
