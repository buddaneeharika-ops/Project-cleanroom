@echo off
echo ===================================================
echo Setting up Nightly Votex Cache Sync (2:00 AM)
echo ===================================================

:: Check for admin privileges (required to create tasks)
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Administrative permissions required. 
    echo Please right-click this script and select "Run as administrator".
    pause
    exit /b 1
)

:: Define Paths
set SCRIPT_DIR=%~dp0
set SCRIPT_PATH=%SCRIPT_DIR%robust_sync.py
set LOG_PATH=%SCRIPT_DIR%nightly_sync.log

:: Create the scheduled task
schtasks /create /tn "Votex_Nightly_Sync" /tr "cmd.exe /c cd /d \"%SCRIPT_DIR%\" && python robust_sync.py >> \"%LOG_PATH%\" 2>&1" /sc daily /st 02:00 /ru "SYSTEM" /f

if %errorLevel% equ 0 (
    echo.
    echo [SUCCESS] Scheduled task "Votex_Nightly_Sync" created successfully!
    echo It will run automatically every day at 2:00 AM.
    echo Logs will be written to: %LOG_PATH%
) else (
    echo.
    echo [FAILED] Failed to create the scheduled task. Check the error above.
)

pause
