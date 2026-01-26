@echo off
REM Zip files needed for Minimal App deployment
REM Usage: Run from the project root directory, or this script will cd there

setlocal

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0

REM Navigate to project root (two levels up from deploy-scripts/zip/)
cd /d "%SCRIPT_DIR%..\.."

echo.
echo ========================================
echo  Zipping Minimal App for Deployment
echo ========================================
echo.

REM Ask about .env
set INCLUDE_ENV=N
set /p INCLUDE_ENV="Include .env file? (y/N): "

REM Set output filename with timestamp
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set TIMESTAMP=%datetime:~0,8%-%datetime:~8,4%
set OUTPUT=deploy-minimal-%TIMESTAMP%.zip

REM Remove old zip if exists
if exist "%OUTPUT%" del "%OUTPUT%"

echo.
echo Creating %OUTPUT%...
echo.
echo Including:
echo   - app.py
echo   - requirements.txt
echo   - core\
echo   - templates\
echo   - static\

if /i "%INCLUDE_ENV%"=="Y" (
    echo   - .env
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'app.py','requirements.txt','core','templates','static','.env' -DestinationPath '%OUTPUT%' -Force"
) else (
    echo   - .env [SKIPPED]
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'app.py','requirements.txt','core','templates','static' -DestinationPath '%OUTPUT%' -Force"
)

echo.

if exist "%OUTPUT%" (
    echo ========================================
    echo  SUCCESS: Created %OUTPUT%
    echo ========================================
    echo.
    echo File size:
    for %%A in ("%OUTPUT%") do echo   %%~zA bytes
    echo.
    echo To deploy to PythonAnywhere:
    echo   1. Upload this zip via Files page
    echo   2. Open Bash console
    echo   3. Run: unzip %OUTPUT%
    echo.
) else (
    echo ERROR: Failed to create zip file
    echo.
)

endlocal
pause
