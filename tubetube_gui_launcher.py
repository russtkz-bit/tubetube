"""Точка входа для PyInstaller: собирает GUI-версию tubetube в один
исполняемый файл (.exe на Windows, обычный бинарник на Linux/macOS)."""

from tubetube.gui import main

if __name__ == "__main__":
    raise SystemExit(main())
