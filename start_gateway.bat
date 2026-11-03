@echo off
title APEX Local AI Gateway (PostgreSQL & LAN Mode)
echo ========================================================
echo        Starting APEX Local AI Gateway
echo        PostgreSQL: TestingDBCodingagent on port 5432
echo        Browser URL: http://localhost:8000/docs
echo ========================================================
cd /d "%~dp0"
.\.venv\Scripts\python.exe apex-gateway\run.py
pause

