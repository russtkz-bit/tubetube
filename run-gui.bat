@echo off
REM Запуск графического интерфейса tubetube в Windows без сборки .exe.
setlocal

set DIR=%~dp0
set VENV=%DIR%.venv

if not exist "%VENV%\Scripts\python.exe" (
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo.
        echo Не удалось создать виртуальное окружение. Убедитесь, что Python
        echo установлен и добавлен в PATH ^(и что при установке отмечена
        echo галочка "tcl/tk and IDLE" — она нужна для графического интерфейса^).
        pause
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
    pause
    exit /b 1
)

REM Запускаем через python.exe (не pythonw.exe): если что-то пойдёт не так,
REM в окне будет видна ошибка, а не молчаливое закрытие без единого сообщения.
"%VENV%\Scripts\python.exe" -m tubetube.gui
if errorlevel 1 (
    echo.
    echo tubetube завершился с ошибкой ^(см. сообщение выше^).
    pause
)
