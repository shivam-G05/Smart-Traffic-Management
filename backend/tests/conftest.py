import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent

for path in (_REPO_ROOT, _BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
