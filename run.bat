@echo off
REM Запуск tubetube в Windows: создаёт venv при первом запуске,
REM ставит зависимости и передаёт все аргументы в программу.
setlocal

set DIR=%~dp0
set VENV=%DIR%.venv

if not exist "%VENV%" (
    python -m venv "%VENV%"
    "%VENV%\Scripts\pip.exe" install --quiet --upgrade pip
    "%VENV%\Scripts\pip.exe" install --quiet -r "%DIR%requirements.txt"
)

"%VENV%\Scripts\python.exe" -m tubetube.cli %*
