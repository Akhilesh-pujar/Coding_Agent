@echo off
title APEX Local AI Gateway (LAN Mode)
echo ========================================================
echo        Starting APEX Local AI Gateway
echo        Host: 0.0.0.0 (Accessible across LAN)
echo        Port: 8000
echo ========================================================
cd /d "%~dp0"
.\.venv\Scripts\python.exe apex-gateway\run.py
pause

