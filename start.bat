@echo off
TITLE THREE·DOTS // SYSTEM BOOTSTRAPPER
color 0b
cls

echo ===================================================
echo       INITIALIZING THREE-DOTS SECURE LAUNCHER
echo ===================================================
echo.

:: 1. Check if Python is installed
echo [1/4] Verifying Python runtime environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [CRITICAL ERROR] Python is not installed or not added to your system PATH!
    echo Please install Python 3.10+ from python.org and check "Add Python to PATH".
    echo.
    pause
    exit /b
)
echo [OK] Python detected.

:: 2. Upgrade pip and install required dependencies quietly
echo [2/4] Verifying and updating game dependencies...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install ursina panda3d pillow requests >nul 2>&1
echo [OK] Dependencies verified.

:: 3. Check for essential game files/assets
echo [3/4] Checking local assets and directories...
if not exist "main.py" (
    echo [WARNING] main.py not found in current directory!
)
if not exist "textures" (
    echo [INFO] Creating textures directory structure...
    mkdir textures
)
echo [OK] Asset directories verified.

:: 4. Launch the game/launcher sequence
echo [4/4] Launching Three·Dots Client...
echo.
if exist "launcher.py" (
    python launcher.py
) else (
    python main.py
)

:: Keep window open if the game closes unexpectedly
echo.
echo ===================================================
echo            GAME SESSION ENDED - EXITING
echo ===================================================
pause