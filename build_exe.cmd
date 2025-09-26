@echo off
setlocal
py -3 -m pip install --upgrade pip
py -3 -m pip install pyinstaller
py -3 -m PyInstaller --noconfirm tsla_trader.spec
echo.
echo Build complete. Find your EXE under .\dist\TSLA Two-Ticker Trader\
endlocal
