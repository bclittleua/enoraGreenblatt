from pathlib import Path
import sys
import curses

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

for p in (BASE_DIR, DATA_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import start_game_v64 as launcher

if __name__ == "__main__":
    curses.wrapper(launcher.main)
    launcher.launch_game(
        getattr(launcher.main, "load_path", None),
        getattr(launcher.main, "no_autopause", False),
    )