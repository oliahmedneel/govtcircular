@echo off
REM ============================================
REM JobSite — Run Script
REM ============================================
echo.
echo ============================================
echo    JobSite — Starting Pipeline
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

REM Start the watcher
python main.py %*
if %errorlevel% neq 0 (
    echo [ERROR] JobSite exited with error.
    pause
    exit /b 1
)