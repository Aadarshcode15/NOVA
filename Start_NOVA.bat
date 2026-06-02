@echo off
title N.O.V.A — Neural Operative Virtual Assistant
cd /d "%~dp0"
echo Starting NOVA...
call .venv\Scripts\activate.bat
python main.py
pause
