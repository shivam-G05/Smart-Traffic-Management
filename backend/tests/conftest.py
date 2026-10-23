import os
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent

for path in (_REPO_ROOT, _BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Tests that spin up the FastAPI app (TestClient) trigger the real lifespan,
# which initializes a database — point that at an isolated in-memory SQLite
# DB rather than the real traffic.db file the dev server writes to. Must be
# set before app.core.config.settings (a module-level singleton) is
# imported anywhere, which conftest.py's early collection guarantees.
os.environ.setdefault("STMS_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
