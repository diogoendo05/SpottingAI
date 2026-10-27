@echo off
TITLE SpottingAI - Servidor Web
cd /d "%~dp0"

echo =======================================================================
echo         SpottingAI - Servidor Web (Navegador)
echo =======================================================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual nao encontrado. Execute run.bat primeiro.
    pause
    exit /b 1
)

start "" "http://localhost:8000"
.\venv\Scripts\python.exe app.py

pause
