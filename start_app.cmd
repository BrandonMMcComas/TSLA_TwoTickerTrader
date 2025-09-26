@echo off
setlocal ENABLEDELAYEDEXPANSION
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

if not exist ".venv" (
  echo Creating virtual environment...
  py -3 -m venv .venv
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt

REM Launch console + GUI
python -m app.main
endlocal
