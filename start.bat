@echo off
echo ========================================
echo   Hienfeld VB Converter - Starting...
echo ========================================
echo.

:: Start backend in new window
echo [1/2] Starting Backend (FastAPI) on port 8000...
start "Backend - FastAPI" cmd /k "cd /d %~dp0 && uvicorn hienfeld_api.app:app --reload --port 8000"

:: Wait a moment for backend to initialize
timeout /t 3 /nobreak > nul

:: Start frontend in new window
echo [2/2] Starting Frontend (Vite) on port 8080...
start "Frontend - Vite" cmd /k "cd /d %~dp0 && npm run dev"

echo.
echo ========================================
echo   Ready! Open in browser:
echo   http://localhost:8080
echo ========================================
echo.
echo Press any key to open browser...
pause > nul
start http://localhost:8080
