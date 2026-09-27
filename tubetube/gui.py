"""Графический интерфейс tubetube (Tkinter — входит в стандартную
поставку Python, отдельно ставить ничего не нужно)."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Callable

from .downloader import (
    DownloadError,
    OperationCancelled,
    download_subtitles,
    list_available_languages,
)
from .updater import UpdateError, current_version, git_pull, is_git_checkout, update_yt_dlp

APP_TITLE = "tubetube — субтитры YouTube"


class TubetubeApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(APP_TITLE)
        root.geometry("720x560")
        root.minsize(640, 480)

        self._log_queue: "queue.Queue[str]" = queue.Queue()
        self._ui_queue: "queue.Queue[Callable[[], None]]" = queue.Queue()
        self._worker: threading.Thread | None = None
        self._cancel_event: threading.Event | None = None

        self._build_widgets()
        self.root.after(100, self._poll_queues)

    # ------------------------------------------------------------------ UI

    def _build_widgets(self) -> None:
        pad = {"padx": 8, "pady": 4}

        form = ttk.Frame(self.root)
        form.pack(fill="x", **pad)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Ссылка на видео или плейлист:").grid(row=0, column=0, sticky="w")
        self.url_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.url_var).grid(row=0, column=1, columnspan=3, sticky="ew", **pad)

        ttk.Label(form, text="Языки (через запятую, или 'all'):").grid(row=1, column=0, sticky="w")
        self.langs_var = tk.StringVar(value="ru,en")
        ttk.Entry(form, textvariable=self.langs_var, width=20).grid(row=1, column=1, sticky="w", **pad)

        ttk.Label(form, text="Папка для сохранения:").grid(row=2, column=0, sticky="w")
        self.output_var = tk.StringVar(value=str(Path.cwd() / "subtitles"))
        ttk.Entry(form, textvariable=self.output_var).grid(row=2, column=1, columnspan=2, sticky="ew", **pad)
        ttk.Button(form, text="Обзор...", command=self._choose_folder).grid(row=2, column=3, **pad)

        type_frame = ttk.LabelFrame(form, text="Тип субтитров")
        type_frame.grid(row=3, column=0, columnspan=4, sticky="ew", **pad)
        self.type_var = tk.StringVar(value="both")
        for i, (value, label) in enumerate([
            ("both", "Авторские + автоматические"),
            ("manual", "Только авторские"),
            ("auto", "Только автоматические"),
        ]):
            ttk.Radiobutton(type_frame, text=label, value=value, variable=self.type_var).grid(
                row=0, column=i, sticky="w", padx=8, pady=2
            )

        format_frame = ttk.LabelFrame(form, text="Формат сохранения")
        format_frame.grid(row=4, column=0, columnspan=4, sticky="ew", **pad)
        self.format_var = tk.StringVar(value="srt")
        for i, (value, label) in enumerate([
            ("srt", "SRT"),
            ("vtt", "VTT"),
            ("txt", "Обычный текст (TXT)"),
        ]):
            ttk.Radiobutton(format_frame, text=label, value=value, variable=self.format_var).grid(
                row=0, column=i, sticky="w", padx=8, pady=2
            )

        self.keep_vtt_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            form, text="Не удалять промежуточный .vtt", variable=self.keep_vtt_var
        ).grid(row=5, column=0, columnspan=2, sticky="w", **pad)

        buttons = ttk.Frame(self.root)
        buttons.pack(fill="x", **pad)
        self.langs_button = ttk.Button(buttons, text="Показать доступные языки", command=self._on_list_langs)
        self.langs_button.pack(side="left", padx=4)
        self.download_button = ttk.Button(buttons, text="Скачать субтитры", command=self._on_download)
        self.download_button.pack(side="left", padx=4)
        self.cancel_button = ttk.Button(buttons, text="Отмена", command=self._on_cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=4)
        self.open_folder_button = ttk.Button(buttons, text="Открыть папку", command=self._open_output_folder)
        self.open_folder_button.pack(side="left", padx=4)
        self.update_button = ttk.Button(
            buttons, text="Обновить yt-dlp", command=self._on_update_yt_dlp
        )
        self.update_button.pack(side="left", padx=4)
        self._git_pull_available = is_git_checkout()
        self.git_pull_button = ttk.Button(
            buttons, text="Обновить tubetube (git pull)", command=self._on_git_pull
        )
        self.git_pull_button.pack(side="left", padx=4)
        if not self._git_pull_available:
            self.git_pull_button.configure(state="disabled")

        self.version_var = tk.StringVar(value=f"yt-dlp: {current_version()}")
        ttk.Label(buttons, textvariable=self.version_var, anchor="e").pack(side="right", padx=4)

        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        self.progress.pack(fill="x", padx=8, pady=(0, 4))

        log_frame = ttk.LabelFrame(self.root, text="Ход выполнения")
        log_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.log_widget = scrolledtext.ScrolledText(log_frame, state="disabled", wrap="word")
        self.log_widget.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value="Готово")
        ttk.Label(self.root, textvariable=self.status_var, anchor="w").pack(fill="x", padx=8, pady=(0, 4))

    # --------------------------------------------------------------- logic

    def _choose_folder(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.output_var.get() or str(Path.cwd()))
        if folder:
            self.output_var.set(folder)

    def _open_output_folder(self) -> None:
        import os
        import subprocess
        import sys

        path = Path(self.output_var.get())
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _log(self, message: str) -> None:
        self._log_queue.put(message)

    def _post(self, fn: Callable[[], None]) -> None:
        """Планирует fn на выполнение в главном (GUI) потоке.

        Tkinter не гарантированно потокобезопасен при прямом вызове его
        методов (в т.ч. root.after) из фонового потока — это иногда
        приводит к редкой гонке ("main thread is not in main loop").
        Поэтому все действия из фоновых потоков идут через эту очередь,
        которую опрашивает только главный поток (см. _poll_queues).
        """
        self._ui_queue.put(fn)

    def _poll_queues(self) -> None:
        try:
            while True:
                message = self._log_queue.get_nowait()
                self.log_widget.configure(state="normal")
                self.log_widget.insert("end", message + "\n")
                self.log_widget.see("end")
                self.log_widget.configure(state="disabled")
        except queue.Empty:
            pass
        try:
            while True:
                fn = self._ui_queue.get_nowait()
                fn()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queues)

    def _set_busy(self, busy: bool, status: str, cancellable: bool = False) -> None:
        state = "disabled" if busy else "normal"
        self.langs_button.configure(state=state)
        self.download_button.configure(state=state)
        self.update_button.configure(state=state)
        self.git_pull_button.configure(
            state=state if (not busy and self._git_pull_available) else "disabled"
        )
        self.cancel_button.configure(state="normal" if (busy and cancellable) else "disabled")
        self.status_var.set(status)
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()
        if not busy:
            self._cancel_event = None

    def _run_in_thread(self, target) -> None:
        if self._worker and self._worker.is_alive():
            messagebox.showinfo(APP_TITLE, "Дождитесь завершения текущей операции.")
            return
        self._worker = threading.Thread(target=target, daemon=True)
        self._worker.start()

    def _run_cancellable_in_thread(self, target) -> "threading.Event | None":
        """Как _run_in_thread, но заводит cancel_event и передаёт его в target(cancel_event)."""
        if self._worker and self._worker.is_alive():
            messagebox.showinfo(APP_TITLE, "Дождитесь завершения текущей операции.")
            return None
        cancel_event = threading.Event()
        self._cancel_event = cancel_event
        self._worker = threading.Thread(target=target, args=(cancel_event,), daemon=True)
        self._worker.start()
        return cancel_event

    def _on_cancel(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()
            self.cancel_button.configure(state="disabled")
            self.status_var.set("Отмена...")
            self._log("Запрошена отмена — операция остановится при первой возможности...")

    def _get_langs(self) -> list[str]:
        raw = self.langs_var.get().strip()
        if raw.lower() == "all":
            return ["all"]
        return [lang.strip() for lang in raw.split(",") if lang.strip()] or ["ru", "en"]

    def _on_list_langs(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning(APP_TITLE, "Укажите ссылку на видео или плейлист.")
            return

        def task(cancel_event):
            self._post(lambda: self._set_busy(True, "Получение списка языков...", cancellable=True))
            final_status = "Готово"
            try:
                manual, auto = list_available_languages(url, on_log=self._log, cancel_event=cancel_event)
                self._log("")
                self._log("Авторские субтитры (manual): " + (", ".join(sorted(manual)) or "нет"))
                self._log("Автоматические субтитры (auto): " + (", ".join(sorted(auto)) or "нет"))
            except OperationCancelled as exc:
                self._log(f"Отменено: {exc}")
                final_status = "Отменено"
            except DownloadError as exc:
                self._log(f"Ошибка: {exc}")
                self._post(lambda exc=exc: messagebox.showerror(APP_TITLE, str(exc)))
                final_status = "Ошибка"
            finally:
                self._post(lambda s=final_status: self._set_busy(False, s))

        self._run_cancellable_in_thread(task)

    def _on_download(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning(APP_TITLE, "Укажите ссылку на видео или плейлист.")
            return
        output_dir = self.output_var.get().strip() or "subtitles"
        langs = self._get_langs()
        sub_type = self.type_var.get()
        fmt = self.format_var.get()
        keep_vtt = self.keep_vtt_var.get()

        def task(cancel_event):
            self._post(lambda: self._set_busy(True, "Скачивание субтитров...", cancellable=True))
            final_status = "Готово"
            try:
                self._log(f"Начинаю: {url}")
                results = download_subtitles(
                    url=url,
                    output_dir=output_dir,
                    langs=langs,
                    sub_type=sub_type,
                    fmt=fmt,
                    keep_vtt=keep_vtt,
                    on_log=self._log,
                    cancel_event=cancel_event,
                )
                self._log("")
                self._log(f"Готово. Сохранено файлов: {len(results)}")
                for path in results:
                    self._log(f"  - {path}")
                self._post(
                    lambda: messagebox.showinfo(
                        APP_TITLE, f"Готово! Сохранено файлов субтитров: {len(results)}"
                    )
                )
            except OperationCancelled as exc:
                self._log(f"Отменено: {exc}")
                final_status = "Отменено"
            except DownloadError as exc:
                self._log(f"Ошибка: {exc}")
                self._post(lambda exc=exc: messagebox.showerror(APP_TITLE, str(exc)))
                final_status = "Ошибка"
            finally:
                self._post(lambda s=final_status: self._set_busy(False, s))

        self._run_cancellable_in_thread(task)

    def _on_update_yt_dlp(self) -> None:
        def task():
            self._post(lambda: self._set_busy(True, "Обновление yt-dlp..."))
            try:
                result = update_yt_dlp(on_log=self._log)
                self._post(lambda: self.version_var.set(f"yt-dlp: {current_version()} (см. лог)"))
                self._post(lambda: messagebox.showinfo(APP_TITLE, result))
            except UpdateError as exc:
                self._log(f"Ошибка обновления: {exc}")
                self._post(lambda exc=exc: messagebox.showerror(APP_TITLE, str(exc)))
            finally:
                self._post(lambda: self._set_busy(False, "Готово"))

        self._run_in_thread(task)

    def _on_git_pull(self) -> None:
        def task():
            self._post(lambda: self._set_busy(True, "Обновление кода tubetube..."))
            try:
                result = git_pull(on_log=self._log)
                self._post(lambda: messagebox.showinfo(APP_TITLE, result))
            except UpdateError as exc:
                self._log(f"Ошибка обновления: {exc}")
                self._post(lambda exc=exc: messagebox.showerror(APP_TITLE, str(exc)))
            finally:
                self._post(lambda: self._set_busy(False, "Готово"))

        self._run_in_thread(task)


def main() -> int:
    root = tk.Tk()
    TubetubeApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
