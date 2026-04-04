@echo off
title Nexus AI - Starting...

echo.
echo  *** Nexus AI - Single Launch ***
echo  Opening http://localhost:8008 in 3 seconds...
echo.

:: Activate venv if it exists, otherwise use system Python
if exist "%~dp0backend\venv\Scripts\activate.bat" (
    call "%~dp0backend\venv\Scripts\activate.bat"
)

:: Install fastapi[standard] to ensure StaticFiles is available (aiofiles)
echo  Checking dependencies...
pip install "fastapi[standard]" uvicorn aiofiles --quiet

:: Change into backend directory (token.json, credentials.json are there)
cd /d "%~dp0backend"

:: Open browser after a short delay
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8008"

:: Start the server
echo.
echo  Server starting at http://localhost:8008
echo  Press Ctrl+C to stop.
echo.
python -m uvicorn backend:app --host 0.0.0.0 --port 8008 --reload
