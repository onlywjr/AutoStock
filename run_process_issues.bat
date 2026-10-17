@echo off
REM AutoStock process_issues scheduled task
set "REPO=C:\My_Project\Hermes\[¤u§@°Ï]\AutoStock"
set "PY=C:\Users\Administrator\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
if not exist "%REPO%\logs" mkdir "%REPO%\logs"
echo === run at %date% %time% === >> "%REPO%\logs\process_issues.log"
"%PY%" "%REPO%\process_issues.py" >> "%REPO%\logs\process_issues.log" 2>&1
