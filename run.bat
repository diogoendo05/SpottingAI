@echo off
TITLE SpottingAI - Sistema de Monitoramento Continuo
cd /d "%~dp0"

echo =======================================================================
echo         SpottingAI - Sistema de Monitoramento Continuo
echo =======================================================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo [1/2] Criando ambiente virtual Python...
    python -m venv venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual. Verifique se o Python esta instalado.
        pause
        exit /b 1
    )
    echo Instalando dependencias iniciais...
    .\venv\Scripts\pip.exe install -r requirements.txt
)

rem Ambientes criados antes do suporte ao drone nao tem o PyAV (decodificador H.264).
.\venv\Scripts\python.exe -c "import av" 2>nul
if errorlevel 1 (
    echo Instalando PyAV para receber o video do drone...
    .\venv\Scripts\pip.exe install "av>=14.0.0"
)

echo [2/2] Iniciando SpottingAI - Acelerado GPU Intel Iris Xe...
echo Feche a janela do aplicativo para encerrar.
echo.

.\venv\Scripts\python.exe desktop.py

if errorlevel 1 (
    echo.
    echo [ERRO] Ocorreu uma falha na execucao do SpottingAI.
    pause
)
