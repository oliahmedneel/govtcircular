@echo off
REM ============================================
REM JobSite — Windows Setup Script
REM ============================================
echo.
echo ============================================
echo    JobSite — Setup Script
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed.
    echo Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)
echo [OK] Python ^(%python --version^)

REM Create virtual environment
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
)

REM Activate and install dependencies
echo Installing dependencies...
call .venv\Scripts\activate.bat
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo [OK] Dependencies installed

REM Create .env if not exists
if not exist ".env" (
    copy .env.example .env >nul
    echo [OK] .env file created. Edit it to add your GEMINI_API_KEY.
) else (
    echo [OK] .env file exists
)

REM Run setup
echo Running project setup...
python main.py --setup
if %errorlevel% neq 0 (
    echo [ERROR] Project setup failed.
    pause
    exit /b 1
)
echo [OK] Project setup complete

echo.
echo ============================================
echo    JobSite is ready to use!
echo.
echo    Commands:
echo      python main.py           Start file watcher
echo      python main.py --once FILE  Process a single file
echo      python main.py --setup     Run setup again
echo.
echo    Don't forget to edit .env with your
echo    GEMINI_API_KEY!
echo ============================================
pause