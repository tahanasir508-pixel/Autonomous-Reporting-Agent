@echo off
cd /d "C:\Users\esam\Desktop\Report Generation Automation"
if not exist logs mkdir logs
"C:\Users\esam\Desktop\Report Generation Automation\venv\Scripts\python.exe" -u run_daily_report.py >> logs\run_log.txt 2>&1
set PYEXIT=%ERRORLEVEL%
echo ---------------------------------------- >> logs\run_log.txt
exit /b %PYEXIT%
