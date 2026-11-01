@echo off
rem Double-click to run Agentic QE Platform. Needs Python 3.12+, Node.js 20+, and Git.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3 scripts\dev.py up) else (python scripts\dev.py up)
if errorlevel 1 pause
