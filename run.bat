@echo off
TITLE SentinelAI - Sistema de Visao Computacional para Seguranca
echo =======================================================================
echo               SentinelAI - Inicializador Automatico
echo =======================================================================
echo.

if not exist venv (
    echo [1/3] Criando ambiente virtual Python (venv)...
    python -m venv venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual. Verifique se o Python esta instalado e no PATH.
        pause
        exit /b 1
    )
) else (
    echo [1/3] Ambiente virtual 'venv' ja existe.
)

echo [2/3] Ativando ambiente virtual e verificando dependencias...
call .\venv\Scripts\activate.bat

echo Instalando/Atualizando dependencias do requirements.txt...
pip install -r requirements.txt
if errorlevel 1 (
    echo [AVISO] Houve um problema na instalacao de dependencias. Tentando iniciar assim mesmo...
)

echo.
echo [3/3] Iniciando o servidor SentinelAI...
echo O painel abrira automaticamente em http://localhost:8000
echo Pressione Ctrl+C nesta janela para encerrar o sistema.
echo.

rem Abre o navegador assim que o servidor terminar de subir.
start "" cmd /c "timeout /t 5 /nobreak >nul & start http://localhost:8000"

python app.py

pause
