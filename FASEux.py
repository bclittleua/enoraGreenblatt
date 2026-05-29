# FASEux.py
from pathlib import Path
import sys
import runpy

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

for p in (BASE_DIR, DATA_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

if __name__ == "__main__":
    runpy.run_module("ux_curses_v112", run_name="__main__")
