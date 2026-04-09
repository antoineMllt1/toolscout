@echo off
echo ===================================
echo  ToolScout - Demarrage du serveur
echo ===================================
echo.

echo [1/3] Installation des dependances Python...
pip install -r "%~dp0backend\requirements.txt" --quiet

echo.
echo [2/3] Build du frontend React...
cd /d "%~dp0frontend-react"
call npm install --silent
call npm run build

echo.
echo [3/3] Lancement du serveur sur http://127.0.0.1:8000
echo.
echo Ouvrez votre navigateur sur : http://127.0.0.1:8000
echo Appuyez sur Ctrl+C pour arreter.
echo.

cd /d "%~dp0backend"
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
