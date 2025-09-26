@echo off
setlocal
REM Manual sentiment run helper
REM Usage: run_sentiment_once.cmd [am|pm|auto] [--keep-weekends]
set MODE=%1
if "%MODE%"=="" set MODE=auto
call ".venv\Scripts\activate.bat"
python -m app.tools.run_sentiment_once --%MODE% %2
endlocal
