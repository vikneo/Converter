"""
Сборка .exe (и не только) через PyInstaller.

Установка:
    pip install -r requirements-dev.txt

Запуск:
    python scripts/build_exe.py
    python scripts/build_exe.py --onefile     # один файл (по умолчанию)
    python scripts/build_exe.py --onedir      # папка с зависимостями (быстрее стартует)
    python scripts/build_exe.py --icon assets/icon.ico
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "dec_to_hex_gui.py"
DIST = ROOT / "dist"
BUILD = ROOT / "build" / "_pyinstaller"


def _default_icon() -> Path | None:
    """Возвращает подходящую иконку для текущей ОС или None."""
    if sys.platform.startswith("win"):
        p = ROOT / "assets" / "icon.ico"
    elif sys.platform == "darwin":
        p = ROOT / "assets" / "icon.icns"
    else:
        p = ROOT / "assets" / "icon.png"
    return p if p.exists() else None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Сборка dec_to_hex через PyInstaller")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--onefile", action="store_true", default=True,
                      help="Собрать единый .exe (по умолчанию)")
    mode.add_argument("--onedir", action="store_true",
                      help="Собрать папку с .exe и зависимостями")
    p.add_argument("--icon", type=str, default=None,
                   help="Путь к .ico (Windows) или .icns (macOS)")
    p.add_argument("--clean", action="store_true",
                   help="Очистить build/ и dist/ перед сборкой")
    return p.parse_args()


def check_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller не установлен. Установи:", file=sys.stderr)
        print("    pip install -r requirements-dev.txt", file=sys.stderr)
        sys.exit(1)


def clean() -> None:
    for p in (DIST, BUILD):
        if p.exists():
            print(f"Удаляю {p}")
            shutil.rmtree(p, ignore_errors=True)


def main() -> int:
    args = parse_args()
    check_pyinstaller()

    if args.clean:
        clean()

    if not SCRIPT.exists():
        print(f"Не найден скрипт: {SCRIPT}", file=sys.stderr)
        return 1

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",                       # без консольного окна
        "--name", "dec_to_hex",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--specpath", str(BUILD),
    ]

    cmd.append("--onedir" if args.onedir else "--onefile")
    icon = Path(args.icon) if args.icon else _default_icon()

    if icon:
        cmd += ["--icon", str(icon)]

    # if args.icon:
    #     icon_path = Path(args.icon)
    #     if not icon_path.exists():
    #         print(f"Иконка не найдена: {icon_path}", file=sys.stderr)
    #         return 1
    #     cmd += ["--icon", str(icon_path)]

    # Tkinter подтягивается автоматически, но на всякий случай:
    cmd += ["--hidden-import", "tkinter"]

    cmd.append(str(SCRIPT))

    print("Команда:")
    print("  " + " ".join(cmd))
    print()

    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print("\nСборка завершилась с ошибкой.", file=sys.stderr)
        return result.returncode

    exe_name = "dec_to_hex.exe" if sys.platform.startswith("win") else "dec_to_hex"
    if args.onedir:
        artifact = DIST / "dec_to_hex" / exe_name
    else:
        artifact = DIST / exe_name

    print("\n✓ Готово.")
    print(f"  Артефакт: {artifact}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
