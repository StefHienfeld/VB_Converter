@echo off
echo ========================================
echo   Hienfeld VB Converter - Model Setup
echo ========================================
echo.
echo Dit script downloadt alle ML/NLP modellen.
echo Dit hoeft maar 1x te gebeuren per machine.
echo.

cd /d "%~dp0"

:: Check for virtual environment
if exist .venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo Warning: No virtual environment found, using system Python
)

:: Run setup script
python scripts/setup_models.py

echo.
pause
