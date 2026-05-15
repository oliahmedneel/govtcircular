@echo off
REM ============================================
REM JobSite — Web Dashboard Run Script
REM ============================================
echo.
echo ============================================
echo    JobSite — Starting Web Dashboard
echo ============================================
echo.

REM Check if venv exists
if not exist ".venv" (
    echo [ERROR] Virtual environment not found.
    echo Run scripts\setup.bat first.
    pause
    exit /b 1
)

REM Activate venv
call .venv\Scripts\activate.bat

REM Start the web app
echo Starting web app on http://localhost:5000
python main.py --web
if %errorlevel% neq 0 (
    echo [ERROR] JobSite Web Dashboard exited with error.
    pause
    exit /b 1
)