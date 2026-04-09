@echo off
setlocal

echo ===================================
echo  ToolScout - Demarrage local
echo ===================================
echo.

echo [STEP 1/3] Python dependencies
pip install -r "%~dp0backend\requirements.txt" --quiet
if errorlevel 1 goto :error

echo.
echo [STEP 2/3] Frontend build
cd /d "%~dp0frontend-react"
call npm install --silent
if errorlevel 1 goto :error
call npm run build
if errorlevel 1 goto :error

echo.
echo [STEP 3/3] Backend startup
echo URL    : http://127.0.0.1:8000
echo Logs   : backend + uvicorn en format structure, access logs desactives
echo Reload : les fichiers SQLite sont exclus pour eviter les redemarrages pendant le scraping
echo Stop   : Ctrl+C
echo.

set PYTHONUNBUFFERED=1
cd /d "%~dp0backend"
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload --no-access-log --reload-exclude data.db --reload-exclude "*.db" --reload-exclude "*.db-*" --reload-exclude "__pycache__" --log-config logging.json
goto :eof

:error
echo.
echo [ERROR] Startup aborted. Check the command output above.
exit /b 1
