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

:: Wait for frontend to be ready
timeout /t 5 /nobreak > nul

:: Open browser automatically
start http://localhost:8080

echo.
echo ========================================
echo   Ready! Browser opened at:
echo   http://localhost:8080
echo ========================================
echo.
echo (This window will close in 3 seconds)
timeout /t 3 /nobreak > nul
