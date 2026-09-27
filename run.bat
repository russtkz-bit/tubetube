@echo off
REM Запуск tubetube в Windows: создаёт venv при первом запуске,
REM ставит зависимости и передаёт все аргументы в программу.
setlocal

set DIR=%~dp0
set VENV=%DIR%.venv

if not exist "%VENV%\Scripts\python.exe" (
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo.
        echo Не удалось создать виртуальное окружение. Убедитесь, что Python
        echo установлен и добавлен в PATH.
        exit /b 1
    )
)

REM Всегда (пере)ставим зависимости — это быстро, если они уже установлены,
REM зато чинит окружение, если предыдущая установка не завершилась.
"%VENV%\Scripts\python.exe" -m pip install --quiet --upgrade pip
"%VENV%\Scripts\python.exe" -m pip install --quiet -r "%DIR%requirements.txt"
if errorlevel 1 (
    echo.
    echo Не удалось установить зависимости ^(см. сообщение выше^). Проверьте
    echo подключение к интернету и повторите запуск.
    exit /b 1
)

"%VENV%\Scripts\python.exe" -m tubetube.cli %*
