@echo off
REM AutoStock process_issues scheduled task (background; no window)
set "REPO=C:\My_Project\Hermes\[¤u§@°Ï]\AutoStock"
set "PY=C:\Users\Administrator\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
if not exist "%REPO%\logs" mkdir "%REPO%\logs"
REM Python handles its own logging; discard console output
"%PY%" "%REPO%\process_issues.py" >nul 2>&1
