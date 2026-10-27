@echo off
TITLE SpottingAI - Compilador de Executavel
echo =======================================================================
echo          SpottingAI - Compilador de Executavel Windows (.exe)
echo =======================================================================
echo.

if not exist venv (
    echo [ERRO] Ambiente virtual 'venv' nao encontrado. Execute 'run.bat' primeiro para configurar.
    pause
    exit /b 1
)

echo Ativando ambiente virtual...
call .\venv\Scripts\activate.bat

echo Garantindo que pyinstaller e pywebview estao instalados...
pip install pyinstaller pywebview -q

echo.
echo Iniciando processo de compilacao (pode levar 1 a 3 minutos)...
python build_exe.py

echo.
pause
