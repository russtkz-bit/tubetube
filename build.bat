@echo off
REM Собирает Windows-приложение TubeTube.exe (единый файл, без консоли)
REM с помощью PyInstaller. Запускать в Windows, где установлен Python.
setlocal

set DIR=%~dp0
set VENV=%DIR%.venv-build

if not exist "%VENV%" (
    python -m venv "%VENV%"
)

"%VENV%\Scripts\pip.exe" install --quiet --upgrade pip
"%VENV%\Scripts\pip.exe" install --quiet -r "%DIR%requirements-build.txt"

"%VENV%\Scripts\pyinstaller.exe" ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name TubeTube ^
    --collect-all yt_dlp ^
    --collect-all certifi ^
    "%DIR%tubetube_gui_launcher.py"

echo.
echo Готово: dist\TubeTube.exe
