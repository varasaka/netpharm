@echo off
REM ============================================================
REM  Build the Windows desktop app (.exe). Run this ON WINDOWS.
REM  Requires: Python 3.10-3.12 on PATH.
REM ============================================================
setlocal

echo [1/4] Creating build environment...
python -m venv .build-venv
call .build-venv\Scripts\activate

echo [2/4] Installing dependencies (this can take several minutes)...
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo [3/4] Freezing the app...
pyinstaller packaging\netpharm.spec --noconfirm

echo [4/4] Done.
echo.
echo   Your app is in:  dist\NetworkPharmacology\
echo   Double-click:    dist\NetworkPharmacology\NetworkPharmacology.exe
echo.
echo   Optional, one time only, for the ADME / target-prediction agents:
echo     .build-venv\Scripts\playwright install chromium
echo.
pause
