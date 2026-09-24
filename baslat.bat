@echo off
cd /d "%~dp0"
start "" http://localhost:8765
.venv\Scripts\python server.py
