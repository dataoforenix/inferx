"""Write docs/openapi.json from the FastAPI app (no server needed).

    python scripts/export_openapi.py

Uses the offline test fixtures, so it works even before the real data/categories.csv exists.
The schema does not depend on the data.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import load_settings  # noqa: E402
from app.factory import create_app  # noqa: E402

FIXTURES = BACKEND_DIR / "tests" / "fixtures"
OUT = BACKEND_DIR / "docs" / "openapi.json"


def build_openapi() -> dict:
    settings = dataclasses.replace(
        load_settings(), openai_api_key=None, demo_mode=False, db_enabled=False,  # path list independent of DB_ENABLED (/api/searches/top: see api_contract.md)
        categories_csv=FIXTURES / "categories_test.csv", demo_cache_dir=FIXTURES / "demo_cache",
    )
    return create_app(settings).openapi()


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    spec = build_openapi()
    OUT.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(BACKEND_DIR)} ({len(spec['paths'])} paths)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
