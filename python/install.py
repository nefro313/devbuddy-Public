#!/usr/bin/env python3
"""
DevBuddy one-command setup (Windows / macOS / Linux, no `make` required).

    cd python
    python install.py

Creates the virtual environment, installs the Week 0 dependencies, and scaffolds
python/.env. Prefers uv if it is installed (fast); otherwise falls back to the
built-in venv + pip.

Afterwards: add your OPENROUTER_API_KEY to python/.env, then run `python run.py`.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV = HERE / ".venv"


def run(cmd):
    print("  $ " + " ".join(str(c) for c in cmd))
    subprocess.check_call(cmd, cwd=HERE)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main() -> None:
    print("DevBuddy setup: installing the Week 0 environment...\n")

    if shutil.which("uv"):
        print("Using uv (fast).")
        if VENV.exists():
            print(f"  .venv already exists at {VENV}, skipping creation.")
        else:
            run(["uv", "venv"])
        run(["uv", "pip", "install", "-r", "requirements.txt"])
    else:
        print("uv not found; using python venv + pip.")
        print("(Tip: install uv for faster setups: https://docs.astral.sh/uv/)")
        if VENV.exists():
            print(f"  .venv already exists at {VENV}, skipping creation.")
        else:
            run([sys.executable, "-m", "venv", str(VENV)])
        py = str(venv_python())
        run([py, "-m", "pip", "install", "--upgrade", "pip"])
        run([py, "-m", "pip", "install", "-r", "requirements.txt"])

    env = HERE / ".env"
    if env.exists():
        print("\npython/.env already exists, leaving it untouched.")
    else:
        shutil.copyfile(HERE / ".env.example", env)
        print("\nScaffolded python/.env from .env.example.")

    print("\nSetup complete.")
    print("Next:")
    print("  1. Open python/.env and set OPENROUTER_API_KEY=<your key>")
    print("  2. Run:  python run.py")


if __name__ == "__main__":
    main()
