@echo off
TITLE SpottingAI - Teste com o Drone
cd /d "%~dp0"

echo =======================================================================
echo         SpottingAI - Teste com o Drone
echo =======================================================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual nao encontrado. Execute run.bat primeiro.
    pause
    exit /b 1
)

echo [1/2] Checagem pre-voo (modelos, porta, firewall, Wi-Fi, celular)...
echo.
.\venv\Scripts\python.exe tools\drone_preflight.py --warm
if errorlevel 1 (
    echo.
    echo [ERRO] A checagem encontrou problemas. Corrija os itens [ERRO] acima.
    pause
    exit /b 1
)

echo.
echo [2/2] Iniciando o SpottingAI (a fonte Drone abre sozinha e espera o celular)...
echo No celular: app SpottingAI Drone ^> engrenagem ^> PC ^> Iniciar envio.
echo Feche esta janela para encerrar. Gravacoes ficam em recordings\
echo.
start "" "http://localhost:8000"
.\venv\Scripts\python.exe app.py

pause
