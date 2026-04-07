"""Выбор папки через системный диалог (macOS/Windows) и нормализация пути."""
from __future__ import annotations

from pathlib import Path

from .paths import PROJECT_DIR

def choose_directory_with_dialog(current_path: str) -> str:
    try:
        import tkinter as tk
        from tkinter import TclError, filedialog
    except Exception as error:  # pragma: no cover - depends on system packages
        raise RuntimeError(
            "На этом компьютере не удалось открыть окно выбора папки. Можно ввести путь вручную."
        ) from error

    initial_dir = resolve_initial_directory(current_path)
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        selected_path = filedialog.askdirectory(
            initialdir=initial_dir,
            mustexist=True,
            title="Выберите папку с файлами сотрудников",
        )
        root.update()
    except TclError as error:  # pragma: no cover - depends on GUI availability
        raise RuntimeError(
            "Не получилось открыть системное окно выбора папки. Если нужно, путь можно вставить вручную."
        ) from error
    finally:
        if root is not None:
            root.destroy()

    return str(Path(selected_path).resolve()) if selected_path else ""


def resolve_initial_directory(current_path: str) -> str:
    candidate_paths: list[Path] = []
    raw_path = current_path.strip()
    if raw_path:
        current = Path(raw_path).expanduser()
        candidate_paths.append(current)
        if not current.is_absolute():
            candidate_paths.append((PROJECT_DIR / current).expanduser())

    candidate_paths.extend([PROJECT_DIR, Path.home()])
    for candidate in candidate_paths:
        try:
            if candidate.is_dir():
                return str(candidate.resolve())
        except OSError:
            continue
    return str(PROJECT_DIR)

