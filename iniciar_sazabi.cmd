@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    python main.py
)
if errorlevel 1 (
    echo Nao foi possivel iniciar. Instale Python 3.9+ com Tcl/Tk e adicione Python ao PATH.
    pause
)
