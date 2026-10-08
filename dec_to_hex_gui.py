import csv
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from builtins import staticmethod
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from exceptions import Cancelled

__version__ = "0.1.0"
SETTINGS_PATH = Path.home() / ".dec_to_hex.json"


class DecToHexConverter:
    """Конвертер десятичных чисел из CSV в HEX-формат."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"Dec → Hex конвертер v{__version__}")

        self.root.geometry("600x560")
        self.root.resizable(False, False)

        # --- настройки (загружаем до построения UI) ---
        self.settings = self._load_settings()

        self.input_path = tk.StringVar(value=self.settings.get("input_path", ""))
        self.output_path = tk.StringVar(value=self.settings.get("output_path", ""))
        self.prefix = tk.StringVar(value=self.settings.get("prefix", "2"))
        self.add_header = tk.BooleanVar(value=self.settings.get("add_header", False))
        self.last_dir = self.settings.get("last_dir", str(Path.home()))

        # управление фоновой задачей
        self._worker: threading.Thread | None = None
        self._cancel_flag = threading.Event()
        self._msg_queue: queue.Queue = queue.Queue()

        # путь к последнему успешно созданному файлу
        self._last_output: str | None = None

        self._build_ui()

        # сохраняем настройки при закрытии окна
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # --- Настройки ---

    @staticmethod
    def _load_settings() -> dict:
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
        except FileNotFoundError:
            return {}
        except (json.JSONDecodeError, OSError):
            # битый файл — не роняем приложение, просто игнорируем
            return {}

    def _save_settings(self):
        data = {
            "input_path": self.input_path.get().strip(),
            "output_path": self.output_path.get().strip(),
            "prefix": self.prefix.get(),
            "add_header": bool(self.add_header.get()),
            "last_dir": self.last_dir,
        }
        tmp = str(SETTINGS_PATH) + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, SETTINGS_PATH)
        except OSError:
            # не критично, если не удалось сохранить
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def _on_close(self):
        self._save_settings()
        self.root.destroy()

    # --- UI ---

    def _build_ui(self):
        pad: dict = {"padx": 10, "pady": 5}

        # Входной файл
        frame_in = ttk.LabelFrame(self.root, text="Входной CSV-файл")
        frame_in.pack(fill="x", **pad)

        ttk.Entry(frame_in, textvariable=self.input_path, width=52).pack(
            side="left", padx=10, pady=8
        )
        ttk.Button(frame_in, text="Обзор…", command=self._browse_input).pack(
            side="left", padx=(0, 10)
        )

        # Выходной файл
        frame_out = ttk.LabelFrame(self.root, text="Выходной CSV-файл")
        frame_out.pack(fill="x", **pad)

        ttk.Entry(frame_out, textvariable=self.output_path, width=52).pack(
            side="left", padx=10, pady=8
        )
        ttk.Button(frame_out, text="Сохранить как…", command=self._browse_output).pack(
            side="left", padx=(0, 10)
        )

        # Параметры
        frame_opt = ttk.LabelFrame(self.root, text="Параметры")
        frame_opt.pack(fill="x", **pad)

        ttk.Label(frame_opt, text="Префикс HEX:").grid(
            row=0, column=0, sticky="w", padx=10, pady=6
        )
        ttk.Entry(frame_opt, textvariable=self.prefix, width=5).grid(
            row=0, column=1, sticky="w", padx=(0, 10)
        )
        ttk.Label(
            frame_opt, text="(например: 0x, 2, $, #)"
        ).grid(row=0, column=2, sticky="w", padx=(0, 10))

        ttk.Checkbutton(
            frame_opt,
            text="Добавить заголовок «value_hex»",
            variable=self.add_header,
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=10, pady=(0, 6))

        # Кнопки + прогресс
        frame_action = ttk.Frame(self.root)
        frame_action.pack(fill="x", **pad)

        self.run_btn = ttk.Button(
            frame_action, text="Конвертировать", command=self._run
        )
        self.run_btn.pack(side="left", padx=(0, 5))

        self.cancel_btn = ttk.Button(
            frame_action, text="Отмена", command=self._cancel, state="disabled"
        )
        self.cancel_btn.pack(side="left", padx=(0, 5))

        self.open_btn = ttk.Button(
            frame_action,
            text="Открыть папку с результатом",
            command=self._open_result_folder,
            state="disabled",
        )
        self.open_btn.pack(side="left")

        # Прогресс-бар + текст
        frame_progress = ttk.Frame(self.root)
        frame_progress.pack(fill="x", padx=10, pady=(0, 5))

        self.progress = ttk.Progressbar(
            frame_progress, mode="determinate", maximum=100, value=0
        )
        self.progress.pack(side="left", fill="x", expand=True)

        self.progress_label = ttk.Label(
            frame_progress, text="—", width=18, anchor="e"
        )
        self.progress_label.pack(side="left", padx=(8, 0))

        # Лог
        self.log = tk.Text(self.root, height=12, state="disabled")
        self.log.pack(fill="both", expand=True, **pad)

    def _browse_input(self):
        path = filedialog.askopenfilename(
            initialdir=self.last_dir,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self.input_path.set(path)
            self.last_dir = str(Path(path).parent)
            # авто-имя выходного файла, если ещё не задано
            if not self.output_path.get().strip():
                p = Path(path)
                self.output_path.set(str(p.with_name(p.stem + "_to_hex.csv")))

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            initialdir=self.last_dir,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self.output_path.set(path)
            self.last_dir = str(Path(path).parent)

    def _log(self, msg: str):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _clear_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    def _set_progress(self, current: int, total: int, text: str | None = None):
        if total > 0:
            percent = current * 100 / total
            self.progress["value"] = percent
            if text is None:
                text = f"{current} / {total}  ({percent:.1f}%)"
        else:
            self.progress["value"] = 100
            if text is None:
                text = "—"
        self.progress_label.config(text=text)

    # --- Открыть папку с результатом ---

    def _open_result_folder(self):
        """Открывает системный файловый менеджер на папке с результатом."""
        target = self._last_output
        if not target:
            messagebox.showinfo("Информация", "Результат ещё не создан.")
            return

        path = Path(target)
        folder = path if path.is_dir() else path.parent
        if not folder.exists():
            messagebox.showwarning(
                "Внимание", f"Папка не найдена:\n{folder}"
            )
            return

        try:
            self._open_in_file_manager(str(folder))
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть папку:\n{e}")

    @staticmethod
    def _open_in_file_manager(path: str):
        """Кроссплатформенное открытие папки в системном файловом менеджере."""
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    # --- Фоновая работа ---

    def _run(self):
        in_path = self.input_path.get().strip()
        out_path = self.output_path.get().strip()
        prefix = self.prefix.get().strip()

        if not in_path:
            messagebox.showwarning("Внимание", "Выберите входной файл.")
            return
        if not out_path:
            messagebox.showwarning("Внимание", "Укажите выходной файл.")
            return
        if not Path(in_path).exists():
            messagebox.showerror("Ошибка", f"Файл не найден:\n{in_path}")
            return
        if Path(in_path).resolve() == Path(out_path).resolve():
            messagebox.showerror(
                "Ошибка",
                "Входной и выходной файлы совпадают.\n"
                "Выберите другой выходной файл, чтобы не затереть данные.",
            )
            return

        self._clear_log()
        self._log(f"Конвертация: {in_path} → {out_path}")
        self._log(f"Префикс: «{prefix}»" if prefix else "Префикс: (нет)")
        self._log("")

        self.progress["value"] = 0
        self.progress_label.config(text="Подготовка…")

        # сбрасываем состояние кнопок
        self.run_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.open_btn.config(state="disabled")
        self._last_output = None
        self._cancel_flag.clear()

        # чистим очередь
        while not self._msg_queue.empty():
            try:
                self._msg_queue.get_nowait()
            except queue.Empty:
                break

        self._worker = threading.Thread(
            target=self._worker_convert,
            args=(in_path, out_path, prefix, self.add_header.get()),
            daemon=True,
        )
        self._worker.start()

        self.root.after(50, self._poll_queue)

    def _cancel(self):
        self._cancel_flag.set()
        self._log("… запрошена отмена, ждём завершения текущего шага")
        self.cancel_btn.config(state="disabled")

    def _poll_queue(self):
        try:
            while True:
                msg = self._msg_queue.get_nowait()
                kind = msg.get("kind")

                if kind == "log":
                    self._log(msg["text"])
                elif kind == "progress":
                    self._set_progress(msg["current"], msg["total"])
                elif kind == "phase":
                    self.progress_label.config(text=msg["text"])
                elif kind == "done":
                    self._on_done(msg)
                    return
        except queue.Empty:
            pass

        if self._worker and self._worker.is_alive():
            self.root.after(50, self._poll_queue)
        else:
            self.root.after(50, self._poll_queue)

    def _on_done(self, msg: dict):
        self.run_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self._worker = None

        if msg.get("cancelled"):
            self._log("")
            self._log("✗ Операция отменена пользователем")
            self.progress_label.config(text="отменено")
            return

        if msg.get("error"):
            self._log(f"✗ Ошибка: {msg['error']}")
            messagebox.showerror("Ошибка", msg["error"])
            self.progress_label.config(text="ошибка")
            return

        processed = msg["processed"]
        skipped = msg["skipped"]
        total = msg.get("total", processed + skipped)
        out_path = msg["out_path"]

        self._set_progress(total, total, text=f"{processed} обработано")
        self._log("")
        self._log(f"✓ Готово! Обработано: {processed}, пропущено: {skipped}")
        self._log(f"  Результат: {out_path}")

        # запоминаем результат и активируем кнопку «Открыть папку…»
        self._last_output = out_path
        self.open_btn.config(state="normal")

        # сохраняем настройки (в т.ч. last_dir) после успешной операции
        self._save_settings()

    # --- Воркер (в отдельном потоке) ---

    def _worker_convert(self, in_path: str, out_path: str,
                        prefix: str, add_header: bool):
        """Обёртка над convert() для запуска в отдельном потоке."""
        try:
            self._msg_queue.put({"kind": "phase", "text": "Подсчёт строк…"})

            def log(msg: str):
                self._msg_queue.put({"kind": "log", "text": msg})

            def progress(current: int, total: int):
                self._msg_queue.put({
                    "kind": "progress", "current": current, "total": total
                })

            # сообщим UI общее количество строк, как только узнаем
            # (convert сначала сам считает — перехватим это через progress)
            processed, skipped = self.convert(
                in_path, out_path, prefix,
                add_header=add_header,
                log=log,
                progress=progress,
                cancel_flag=self._cancel_flag,
            )

            # total уже известен внутри, но нам для done он не обязателен —
            # UI получит финальный progress(current, total) перед done
            self._msg_queue.put({
                "kind": "done",
                "processed": processed,
                "skipped": skipped,
                "out_path": out_path,
            })

        except Cancelled:
            self._msg_queue.put({"kind": "done", "cancelled": True})
        except Exception as e:
            self._msg_queue.put({"kind": "done", "error": str(e)})

    @staticmethod
    def convert(
        in_path: str,
        out_path: str,
        prefix: str,
        add_header: bool = False,
        log=lambda msg: None,
        progress=lambda current, total: None,
        cancel_flag: threading.Event | None = None,
    ) -> tuple[int, int]:
        """
        Построчно конвертирует dec → hex.

        Возвращает (processed, skipped).

        - Читает только первую колонку CSV.
        - Пустые/пробельные строки пропускает молча (не считаются ни в processed,
        ни в skipped).
        - Нечисловые и отрицательные значения пропускает с вызовом log().
        - Пишет атомарно: сначала в out_path + ".tmp", потом os.replace.
        - Кодировка: utf-8-sig на входе (съедает BOM), utf-8 на выходе.

        Параметры:
            log      — вызывается со строкой для лога.
            progress — вызывается с (current, total) по ходу обработки.
            cancel_flag — если установлен, операция прерывается (кидает _Cancelled).
        """
        if cancel_flag is None:
            cancel_flag = threading.Event()

        processed = 0
        skipped = 0
        tmp_path = out_path + ".tmp"

        try:
            # считаем строки — нужно для прогресса
            total_lines = DecToHexConverter._count_lines(in_path, cancel_flag)
            progress(0, total_lines)

            with open(tmp_path, "w", newline="", encoding="utf-8") as out_f:
                writer = csv.writer(out_f, lineterminator="\n")
                if add_header:
                    writer.writerow(["value_hex"])

                with open(in_path, newline="", encoding="utf-8-sig") as in_f:
                    reader = csv.reader(in_f)
                    for line_no, row in enumerate(reader, start=1):
                        if line_no % 1000 == 0 and cancel_flag.is_set():
                            raise Cancelled()

                        if not row or not row[0].strip():
                            continue

                        raw = row[0].strip()
                        try:
                            n = int(raw)
                        except ValueError:
                            log(f"  ⚠ Строка {line_no}: «{raw}» — не число, пропуск")
                            skipped += 1
                            progress(processed + skipped, total_lines)
                            continue

                        if n < 0:
                            log(f"  ⚠ Строка {line_no}: «{raw}» — отрицательное, пропуск")
                            skipped += 1
                            progress(processed + skipped, total_lines)
                            continue

                        writer.writerow([f"{prefix}{n:x}".upper()])
                        processed += 1

                        if processed % 500 == 0:
                            progress(processed + skipped, total_lines)

            progress(processed + skipped, total_lines)
            os.replace(tmp_path, out_path)

        except Exception:
            DecToHexConverter._cleanup_tmp(tmp_path)
            raise

        return processed, skipped

    @staticmethod
    def _count_lines(in_path: str, cancel_flag: threading.Event) -> int:
        total = 0
        with open(in_path, newline="", encoding="utf-8-sig") as in_f:
            reader = csv.reader(in_f)
            for line_no, row in enumerate(reader, start=1):
                if line_no % 10000 == 0 and cancel_flag.is_set():
                    raise Cancelled()
                if row and row[0].strip():
                    total += 1
        return total

    @staticmethod
    def _cleanup_tmp(tmp_path: str):
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def main() -> None:
    root = tk.Tk()
    DecToHexConverter(root)
    root.mainloop()


if __name__ == "__main__":
    main()
