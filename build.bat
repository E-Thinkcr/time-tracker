@echo off
REM Genera dist\TimeTracker.exe (un solo archivo, sin consola).
setlocal
cd /d "%~dp0"

python -m pip install --upgrade -r requirements-dev.txt || goto :error
python -m pytest -q || goto :error

python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name TimeTracker app.py || goto :error

echo.
echo Listo: dist\TimeTracker.exe
exit /b 0

:error
echo.
echo Hubo un error. Revisa los mensajes de arriba.
exit /b 1
