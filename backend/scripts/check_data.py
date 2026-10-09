"""Friendly checker for categories.csv. Reports every problem, then scores each category.

    python scripts/check_data.py                       # checks data/categories.csv
    python scripts/check_data.py path/to/file.csv
    python scripts/check_data.py data/categories_template.csv --min 1

Exit code 0 when there are no errors (warnings are fine), 1 otherwise.
The app's loader is stricter in one way: it refuses to start on the first file with errors.
This tool never stops early, so the whole file can be fixed in one pass.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.data_store import MAX_CATEGORIES, MIN_CATEGORIES, Inspection, Issue, inspect_categories  # noqa: E402
from app.schemas import FeasibilityReport  # noqa: E402
from app.scoring import MIN_COMPLETENESS, compute_report  # noqa: E402

DEFAULT_PATH = BACKEND_DIR / "data" / "categories.csv"


def _issue_lines(issue: Issue) -> list[str]:
    where = f"row {issue.row}" if issue.row is not None else "file"
    who = f" [{issue.category_id}]" if issue.category_id else ""
    col = f" {issue.column}" if issue.column else ""
    value = f" = {issue.value!r}" if issue.value else ""
    lines = [f"  {where}{who}{col}{value}", f"      problem: {issue.message}"]
    if issue.fix:
        lines.append(f"      fix:     {issue.fix}")
    return lines


def _components(report: FeasibilityReport) -> str:
    parts = []
    for name, score in (("market", report.market.score), ("cost", report.cost.score),
                        ("feasibility", report.feasibility.score), ("competition", report.competition.score)):
        if score is None:
            parts.append(f"{name}:-")
        elif name == "market" and report.market.trend_score is None:
            parts.append(f"{name}:{score:.1f}(volume only)")
        else:
            parts.append(f"{name}:{score:.1f}")
    return "  ".join(parts)


def _forced_reason(report: FeasibilityReport) -> str:
    off = [n for n, s in (("market", report.market.score), ("cost", report.cost.score),
                          ("feasibility", report.feasibility.score), ("competition", report.competition.score))
           if s is None]
    reason = f"completeness {report.data_completeness:.0%} < {MIN_COMPLETENESS:.0%}"
    return f"{reason}; missing: {', '.join(off)}" if off else reason


def build_report(path: Path, min_categories: int = MIN_CATEGORIES,
                 max_categories: int = MAX_CATEGORIES) -> tuple[str, int, Inspection]:
    """Return (printable text, exit code, inspection). Separated from main() for tests."""
    result = inspect_categories(path, min_categories, max_categories, detailed=True)
    out = [f"Checking {path}", f"{len(result.columns)} columns, {result.row_count} rows", ""]

    errors, warnings = result.errors, result.warnings
    out.append(f"ERRORS ({len(errors)})" + ("" if errors else ": none"))
    for issue in errors:
        out.extend(_issue_lines(issue))
    out.append("")
    out.append(f"WARNINGS ({len(warnings)})" + ("" if warnings else ": none"))
    for issue in warnings:
        out.extend(_issue_lines(issue))
    out.append("")

    verdicts: Counter[str] = Counter()
    if result.records:
        out.append("RESULTS PER CATEGORY (rows with errors are not scored)")
        width = max(len(c) for c in result.records)
        for cid, record in result.records.items():
            report = compute_report(record)
            verdicts[report.verdict] += 1
            score = "-" if report.score is None else f"{report.score:.1f}"
            verdict = (f"MAYBE  FORCED MAYBE ({_forced_reason(report)})" if report.verdict_forced_maybe
                       else report.verdict)
            out.append(f"  {cid:<{width}}  completeness {report.data_completeness:>4.0%}  score {score:>4}  "
                       f"{verdict}")
            out.append(f"  {'':<{width}}  {_components(report)}")
            extra = []
            if report.cost.margin is not None:
                extra.append(f"margin {report.cost.margin:+.3f} (landed {report.cost.landed_cost_per_kg_usd:g} vs "
                             f"local {report.cost.local_cost_per_kg_est_usd:g} USD/kg)")
            if report.verdict_capped_by:
                extra.append(f"CAPPED by {report.verdict_capped_by}")
            if report.flags:
                extra.append("flags: " + ", ".join(report.flags))
            if extra:
                out.append(f"  {'':<{width}}  " + "; ".join(extra))
        out.append("")

    summary = (f"SUMMARY: {verdicts['MANUFACTURE']} MANUFACTURE, {verdicts['MAYBE']} MAYBE, "
               f"{verdicts['DONT']} DONT; {len(errors)} errors, {len(warnings)} warnings")
    out.append(summary)
    if result.records and not verdicts["DONT"]:
        out.append("WARNING: no category scores DONT; the demo needs at least one of each verdict.")
    if result.records and not verdicts["MANUFACTURE"]:
        out.append("WARNING: no category scores MANUFACTURE; the demo needs at least one of each verdict.")
    out.append("RESULT: " + ("FAILED (fix the errors above)" if errors else "OK (the app will load this file)"))
    return "\n".join(out), (1 if errors else 0), result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--min", type=int, default=MIN_CATEGORIES, help="minimum number of categories")
    args = parser.parse_args()
    # Windows consoles default to a legacy code page; Arabic would crash print().
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    text, code, _ = build_report(args.path, min_categories=args.min)
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
