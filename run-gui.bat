@echo off
REM Запуск графического интерфейса tubetube в Windows без сборки .exe.
setlocal

set DIR=%~dp0
set VENV=%DIR%.venv

if not exist "%VENV%" (
    python -m venv "%VENV%"
    "%VENV%\Scripts\pip.exe" install --quiet --upgrade pip
    "%VENV%\Scripts\pip.exe" install --quiet -r "%DIR%requirements.txt"
)

"%VENV%\Scripts\pythonw.exe" -m tubetube.gui
