"""
Runs the REST API for local development against a throwaway database in .dev-data/
(so experimenting never touches databases/). Used by the "backend-dev" preview config.

    python scripts/dev_backend.py            # http://127.0.0.1:8000, Swagger at /docs
    KPI_DB_DIR=databases python scripts/dev_backend.py   # use your real data instead
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("KPI_DB_DIR", str(ROOT / ".dev-data" / "databases"))
os.environ.setdefault("KPI_EXPORT_DIR", str(ROOT / ".dev-data" / "exports"))
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("src.api:app", host="127.0.0.1", port=int(os.environ.get("API_PORT", "8000")))
