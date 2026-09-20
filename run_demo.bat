@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv || goto :error
)
call ".venv\Scripts\activate.bat" || goto :error
python -m pip install --upgrade pip || goto :error
python -m pip install -r requirements.txt || goto :error
python run_demo.py
exit /b 0

:error
echo.
echo No se pudo iniciar la demo. Comprueba que Python 3 esta instalado.
pause
exit /b 1
