"""
Build .exe (and other binaries) via PyInstaller.

Install:
    pip install -e ".[dev]"

Run:
    python scripts/build_exe.py
    python scripts/build_exe.py --onefile     # single file (default)
    python scripts/build_exe.py --onedir      # directory with dependencies
    python scripts/build_exe.py --icon assets/icon.ico
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Windows console defaults to cp1252, which cannot encode non-ASCII
# characters. Force UTF-8 to keep output readable and to avoid
# UnicodeEncodeError if any non-ASCII text sneaks in later.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "dec_to_hex_gui.py"
DIST = ROOT / "dist"
BUILD = ROOT / "build"          # PyInstaller workdir (not the same as scripts/)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build dec_to_hex with PyInstaller")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--onefile",
        action="store_true",
        default=True,
        help="Build a single-file binary (default)",
    )
    mode.add_argument(
        "--onedir",
        action="store_true",
        help="Build a directory with the binary and its dependencies",
    )
    p.add_argument(
        "--icon",
        type=str,
        default=None,
        help="Path to .ico (Windows) or .icns (macOS)",
    )
    p.add_argument(
        "--clean",
        action="store_true",
        help="Clean build/ and dist/ before building",
    )
    return p.parse_args()


def _default_icon() -> Path | None:
    """Pick a platform-appropriate icon, or None if missing."""
    if sys.platform.startswith("win"):
        p = ROOT / "assets" / "icon.ico"
    elif sys.platform == "darwin":
        p = ROOT / "assets" / "icon.icns"
    else:
        p = ROOT / "assets" / "icon.png"
    return p if p.exists() else None


def check_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is not installed. Install it with:", file=sys.stderr)
        print('    pip install -e ".[dev]"', file=sys.stderr)
        sys.exit(1)


def clean() -> None:
    for p in (DIST, BUILD):
        if p.exists():
            print(f"Removing {p}")
            shutil.rmtree(p, ignore_errors=True)


def main() -> int:
    args = parse_args()
    check_pyinstaller()

    if args.clean:
        clean()

    if not SCRIPT.exists():
        print(f"Script not found: {SCRIPT}", file=sys.stderr)
        return 1

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",                       # no console window
        "--name", "dec_to_hex",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--specpath", str(BUILD),
    ]

    cmd.append("--onedir" if args.onedir else "--onefile")

    icon = Path(args.icon) if args.icon else _default_icon()
    if icon:
        if not icon.exists():
            print(f"Icon not found: {icon}", file=sys.stderr)
            return 1
        print(f"Icon: {icon}")
        cmd += ["--icon", str(icon)]

    cmd += ["--hidden-import", "tkinter"]
    cmd.append(str(SCRIPT))

    print("Command:")
    print("  " + " ".join(cmd))
    print()

    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print("\nBuild failed.", file=sys.stderr)
        return result.returncode

    exe_name = "dec_to_hex.exe" if sys.platform.startswith("win") else "dec_to_hex"
    if args.onedir:
        artifact = DIST / "dec_to_hex" / exe_name
    else:
        artifact = DIST / exe_name

    print("\nDone.")
    print(f"  Artifact: {artifact}")

    if sys.platform.startswith("win"):
        print()
        print("  Note: Windows caches icons. If Explorer shows an old one,")
        print("  rename the .exe, move it, or run: ie4uinit.exe -ClearIconCache")

    return 0


if __name__ == "__main__":
    sys.exit(main())
