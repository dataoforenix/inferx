"""Re-pull Jordan's imports from UN Comtrade for every category and write a refreshed copy of the CSV.

    python scripts/refresh_trade_data.py                       # data/categories.csv -> data/categories.refreshed.csv
    python scripts/refresh_trade_data.py --csv path/to/file.csv --out path/to/out.csv

Only imports_2020_usd .. imports_2024_usd and import_weight_kg_2024 are replaced; every other column is copied
unchanged. The original file is never overwritten. A value Comtrade doesn't return keeps its old value.
Prints old / new / % change per value and flags changes over 5%.

Review before installing: run scripts/check_data.py on the refreshed file (import_price_per_kg_usd is NOT
recomputed, so a big change can trigger the price-vs-imports/weight warning), update the "pulled" dates in
source_notes by hand, then copy it over data/categories.csv and update tests/test_real_data.py if verdicts move.

Uses the public preview API (no key), paced slowly (5 s between requests) so it doesn't hit the rate limit:
expect ~25 s per category.

Exit code: 0 = every value refreshed, 2 = written but some values kept their old value, 1 = nothing written.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.comtrade import ComtradeClient  # noqa: E402
from app.schemas import IMPORT_YEARS  # noqa: E402

DEFAULT_CSV = BACKEND_DIR / "data" / "categories.csv"
DEFAULT_OUT = BACKEND_DIR / "data" / "categories.refreshed.csv"
CHANGE_FLAG = 0.05
REFRESH_MIN_INTERVAL = 5.0  # seconds between Comtrade requests (measured: no 429s at this pace)
REFRESH_TIMEOUT = 90.0  # per category
WEIGHT_COLUMN = f"import_weight_kg_{IMPORT_YEARS[-1]}"
TRADE_COLUMNS = [*(f"imports_{y}_usd" for y in IMPORT_YEARS), WEIGHT_COLUMN]


def _float(text: str) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _cell(value: float) -> str:
    return str(round(value))  # the CSV stores whole USD and kg


def _change(old: float | None, new: float | None) -> float | None:
    if old is None or new is None or old == 0:
        return None
    return (new - old) / old


def refresh(rows: list[dict[str, str]], client) -> tuple[list[dict[str, str]], list[tuple], int]:
    """Returns (new rows, table lines, number of values that kept their old value)."""
    table, kept = [], 0
    out_rows = []
    for row in rows:
        new_row = dict(row)
        series = client.fetch(row.get("hs6", ""))
        fresh: dict[str, float | None] = dict.fromkeys(TRADE_COLUMNS)
        if series is not None:
            fresh.update({f"imports_{y}_usd": v for y, v in series.imports_usd.items()})
            fresh[WEIGHT_COLUMN] = series.import_weight_kg_2024
        for column in TRADE_COLUMNS:
            old, new = _float(row.get(column, "")), fresh[column]
            if new is None:
                kept += 1
                table.append((row["category_id"], column, row.get(column, ""), "(not returned: kept)", None, False))
                continue
            new_row[column] = _cell(new)
            change = _change(old, float(new_row[column]))
            flagged = change is None or abs(change) > CHANGE_FLAG
            table.append((row["category_id"], column, row.get(column, ""), new_row[column], change, flagged))
        out_rows.append(new_row)
    return out_rows, table, kept


def print_table(table: list[tuple]) -> None:
    print(f"{'category_id':<20} {'column':<22} {'old':>14} {'new':>22} {'change':>9}")
    for cid, column, old, new, change, flagged in table:
        pct = "" if change is None else f"{change:+.1%}"
        mark = "  <-- over 5%" if flagged and change is not None else ("  <-- check" if flagged else "")
        print(f"{cid:<20} {column:<22} {old:>14} {new:>22} {pct:>9}{mark}")


def main(argv: list[str] | None = None, client=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="categories CSV to read")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="refreshed copy to write")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.out.resolve() == args.csv.resolve():
        print("Refusing to overwrite the input file: choose another --out.")
        return 1
    with args.csv.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames, rows = reader.fieldnames or [], list(reader)
    missing = [c for c in ("category_id", "hs6", *TRADE_COLUMNS) if c not in fieldnames]
    if missing:
        print(f"{args.csv} lacks columns: {', '.join(missing)}")
        return 1

    client = client or ComtradeClient(min_interval=REFRESH_MIN_INTERVAL, total_timeout=REFRESH_TIMEOUT, cache_ttl=0)
    print(f"Fetching {len(rows)} categories from UN Comtrade (about 25 s each)...")
    out_rows, table, kept = refresh(rows, client)
    if kept == len(rows) * len(TRADE_COLUMNS):
        print("UN Comtrade returned nothing (offline or rate-limited?). No file written.")
        return 1

    with args.out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)

    print()
    print_table(table)
    flagged = sum(1 for *_, change, flag in table if flag and change is not None)
    print(f"\nWrote {args.out} ({len(out_rows)} categories; {flagged} values changed by more than 5%; "
          f"{kept} values not returned and kept).")
    print("Next: run scripts/check_data.py on it, update the 'pulled' dates in source_notes by hand, review the "
          "flagged values, then copy it over data/categories.csv.")
    return 2 if kept else 0


if __name__ == "__main__":
    sys.exit(main())
