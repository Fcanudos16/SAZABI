@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "%~dp0iniciar_sazabi.pyw"
) else (
    where pythonw.exe >nul 2>&1
    if errorlevel 1 (
        echo Instale Python 3.9+ com Tcl/Tk e adicione Python ao PATH.
        pause
        exit /b 1
    )
    start "" pythonw.exe "%~dp0iniciar_sazabi.pyw"
)
