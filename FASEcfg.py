# FASEcfg.py
from pathlib import Path
import importlib
import sys

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

for p in (BASE_DIR, DATA_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

_impl = importlib.import_module("config_v49")

for _name, _value in vars(_impl).items():
    if not (_name.startswith("__") and _name.endswith("__")):
        globals()[_name] = _value

__all__ = [
    _name for _name in globals()
    if not (_name.startswith("__") and _name.endswith("__"))
]
