@echo off
echo 🚀 Starting Local LCR Ministering Scraper
echo.

REM Check if virtual environment exists
if not exist venv (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate

REM Install dependencies
echo 📦 Installing dependencies...
pip install -r local_requirements.txt

REM Run the scraper
echo 🚀 Running local scraper...
python local_scraper.py

goto :end

:error
echo.
echo ❌ Setup failed. Please check the error messages above.
pause

:end
echo.
echo 🏁 Local scraper finished.