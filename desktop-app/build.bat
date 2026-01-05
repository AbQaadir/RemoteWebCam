@echo off
echo ========================================
echo Building Remote Webcam Desktop App
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Build with PyInstaller
echo.
echo Building executable...
pyinstaller --clean RemoteWebcam.spec

echo.
echo ========================================
echo Build complete!
echo Executable: dist\RemoteWebcam.exe
echo ========================================

REM Optional: Build installer with Inno Setup
REM Uncomment the following lines if you have Inno Setup installed
REM echo Building installer...
REM "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss

pause
