@echo off
REM process_issues 定時排程腳本
REM 用法: 由 Windows Task Scheduler 每 5~10 分鐘執行一次
REM 確保 gh CLI 已登入且網路連線正常

cd /d "C:\My_Project\Hermes\[工作區]\AutoStock"
python "C:\My_Project\Hermes\[工作區]\AutoStock\process_issues.py" >> "C:\My_Project\Hermes\[工作區]\AutoStock\logs\process_issues.log" 2>&1
