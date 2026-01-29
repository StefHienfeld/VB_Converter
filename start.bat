@echo off
echo ========================================
echo   Hienfeld VB Converter - Starting...
echo ========================================
echo.

:: Change to script directory
cd /d "%~dp0"

:: Start backend in new window
echo [1/2] Starting Backend (FastAPI) on port 8000...

:: Check for virtual environment and start backend
if exist .venv\Scripts\activate.bat goto :use_venv
goto :use_system

:use_venv
echo    Using virtual environment (.venv)...
start "Backend - FastAPI" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate.bat && uvicorn hienfeld_api.app:app --reload --port 8000"
goto :backend_done

:use_system
echo    Using system Python...
start "Backend - FastAPI" cmd /k "cd /d %~dp0 && uvicorn hienfeld_api.app:app --reload --port 8000"
goto :backend_done

:backend_done
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
echo Backend and Frontend are running in separate windows.
echo Press any key to close this window...
pause >nul
