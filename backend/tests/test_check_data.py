"""scripts/check_data.py: every problem reported with a fix, then a per-category score table."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.data_store import inspect_categories, load_categories
from scripts.check_data import build_report
from tests.conftest import TEST_CSV

BACKEND_DIR = Path(__file__).resolve().parent.parent
CHECK_DATA = str(BACKEND_DIR / "scripts" / "check_data.py")  # absolute: works from any working directory


def run(path, **kw):
    text, code, result = build_report(path, **kw)
    return text, code, result


def issues_for(result, column):
    return [i for i in result.issues if column in i.column]


# --- good file -----------------------------------------------------------------------

def test_good_file_passes_with_table_and_summary():
    text, code, result = run(TEST_CSV)
    assert code == 0 and not result.errors
    assert "RESULT: OK" in text
    assert "SUMMARY: 3 MANUFACTURE, 1 MAYBE, 1 DONT; 0 errors" in text
    # glass: landed 0.50 x 1.10 = 0.55 < local 0.75 -> margin -0.364, cost 0 -> 0.35*5.64 + 0.8 + 0.6 = 3.4
    assert "glass_containers" in text and "score  3.4  DONT" in text
    assert "no category scores" not in text


def test_cli_exit_codes_and_arabic_safe_output(csv_frame, write_csv, tmp_path):
    good = subprocess.run([sys.executable, CHECK_DATA, str(TEST_CSV)], capture_output=True, cwd=BACKEND_DIR)
    assert good.returncode == 0 and b"RESULT: OK" in good.stdout
    csv_frame.loc[0, "hs6"] = "12"
    bad = subprocess.run([sys.executable, CHECK_DATA, str(write_csv(csv_frame))], capture_output=True,
                         cwd=BACKEND_DIR)
    assert bad.returncode == 1 and b"RESULT: FAILED" in bad.stdout


# --- error classes ---------------------------------------------------------------------

@pytest.mark.parametrize(
    ("column", "value", "problem", "fix"),
    [
        ("name_ar", "", "name_ar is required", "cannot be empty"),
        ("category_id", "Bad Id", "lowercase snake_case", "lowercase letters"),
        ("hs6", "92410", "must be exactly 6 digits", "stripped a leading zero"),
        ("hs6", "392410.0", "must be exactly 6 digits", "turned the code into a number"),
        ("data_status", "DONE", "data_status must be one of", "VERIFIED, ESTIMATE or TODO_REAL_DATA"),
        ("shipping_pct", "25", "outside", "Looks like 25 instead of 0.25"),
        ("customs_pct", "20%", "is not a number", "Remove the % sign"),
        ("imports_2024_usd", "24,000,000", "is not a number", "thousands separators"),
        ("machinery_availability", "7", "outside", "0 to 5 scale"),
        ("local_factories", "2.5", "whole number", "whole number"),
        ("factories_saturation", "0", "outside", "at least 1"),
        ("import_price_per_kg_usd", "0", "outside", "greater than 0"),
        ("estimated_fields", "shipping_pct;profit", "unknown column names: profit", "exact column names"),
        ("source_url", "www.example.com", "must start with http", "https://"),
    ],
)
def test_each_error_class_has_a_fix(csv_frame, write_csv, column, value, problem, fix):
    csv_frame.loc[0, column] = value
    _, code, result = run(write_csv(csv_frame))
    assert code == 1
    found = [i for i in result.errors if i.column == column]
    assert found, result.errors
    assert problem in found[0].message and fix in found[0].fix
    assert found[0].row == 2 and found[0].value == value


def test_machine_cost_min_above_max(csv_frame, write_csv):
    csv_frame.loc[1, ["machine_cost_jod_min", "machine_cost_jod_max"]] = ["50000", "40000"]
    _, code, result = run(write_csv(csv_frame))
    assert code == 1 and "swap" in issues_for(result, "machine_cost_jod_max")[0].fix


def test_duplicate_ids(csv_frame, write_csv):
    csv_frame.loc[1, "category_id"] = csv_frame.loc[0, "category_id"]
    _, _, result = run(write_csv(csv_frame))
    assert any("duplicate" in i.message and i.row == 3 for i in result.errors)


def test_missing_columns(csv_frame, write_csv):
    text, code, result = run(write_csv(csv_frame.drop(columns=["customs_pct", "hs6"])))
    assert code == 1
    assert any("missing columns: hs6, customs_pct" in i.message for i in result.errors)
    assert "categories_template.csv" in text
    assert not any(i.column == "hs6" and "required" in i.message for i in result.errors)  # no per-row noise


def test_wrong_row_count_still_scores_rows(csv_frame, write_csv):
    text, code, result = run(write_csv(csv_frame.iloc[:2]))
    assert code == 1 and any("between 3 and 20" in i.message for i in result.errors)
    assert len(result.records) == 2 and "RESULTS PER CATEGORY" in text


def test_not_utf8(csv_frame, tmp_path):
    path = tmp_path / "cp1256.csv"
    csv_frame.to_csv(path, index=False, encoding="cp1256")
    _, code, result = run(path)
    assert code == 1 and "CSV UTF-8" in result.errors[0].fix


def test_everything_reported_in_one_pass(csv_frame, write_csv):
    csv_frame.loc[0, "hs6"] = "1"
    csv_frame.loc[0, "customs_pct"] = "x"
    csv_frame.loc[2, "source_url"] = "nope"
    csv_frame.loc[4, "skills_availability"] = "9"
    _, _, result = run(write_csv(csv_frame))
    assert {(i.row, i.column) for i in result.errors} == {
        (2, "hs6"), (2, "customs_pct"), (4, "source_url"), (6, "skills_availability")}


# --- warnings --------------------------------------------------------------------------

def test_year_jump_warning(csv_frame, write_csv):
    csv_frame.loc[0, "imports_2022_usd"] = "900000000"  # neighbours are ~20M
    _, code, result = run(write_csv(csv_frame))
    assert code == 0
    assert any("10x" in i.message and i.column == "imports_2022_usd" for i in result.warnings)


def test_price_mismatch_with_jod_hint(csv_frame, write_csv):
    csv_frame.loc[0, "import_price_per_kg_usd"] = f"{2.5 * 1.41:.3f}"  # 24M / 9.6M = 2.5
    _, _, result = run(write_csv(csv_frame))
    warning = issues_for(result, "import_price_per_kg_usd")[0]
    assert "differs" in warning.message and "JOD" in warning.fix


def test_factories_above_saturation(csv_frame, write_csv):
    csv_frame.loc[0, "local_factories"] = "99"
    _, _, result = run(write_csv(csv_frame))
    assert any("above factories_saturation" in i.message for i in result.warnings)


def test_empty_cell_disabling_a_component_and_forced_maybe(csv_frame, write_csv):
    csv_frame.loc[0, "local_cost_per_kg_est_usd"] = ""
    text, code, result = run(write_csv(csv_frame))
    assert code == 0
    assert any("cost score is switched off" in i.message for i in result.warnings)
    assert "FORCED MAYBE (completeness 70% < 80%; missing: cost)" in text


def test_summary_warns_when_a_verdict_is_missing(csv_frame, write_csv):
    csv_frame.loc[4, "local_factories"] = "0"  # glass: DONT -> MAYBE
    csv_frame.loc[4, "local_cost_per_kg_est_usd"] = "0.4"
    text, _, _ = run(write_csv(csv_frame))
    assert "0 DONT" in text and "no category scores DONT" in text


def test_heuristic_warnings_do_not_reach_the_app(csv_frame, write_csv):
    csv_frame.loc[0, "local_factories"] = "99"
    path = write_csv(csv_frame)
    assert any(i.detailed_only for i in inspect_categories(path, detailed=True).warnings)
    assert not any("above factories_saturation" in w for w in load_categories(path).warnings)


def test_template_checks_clean_with_min_one():
    from tests.test_data_store import TEMPLATE_CSV

    text, code, _ = run(TEMPLATE_CSV, min_categories=1)
    assert code == 0 and "example_product" in text


def test_table_shows_margin_gate_and_flags(csv_frame, write_csv):
    csv_frame.loc[0, "local_cost_per_kg_est_usd"] = "4.2"  # landed 3.0 -> margin -0.4 -> cost gate DONT
    csv_frame.loc[0, "machine_cost_usd_max"] = "300000"
    text, _, _ = run(write_csv(csv_frame))
    assert "margin -0.400 (landed 3 vs local 4.2 USD/kg); CAPPED by cost_gate; flags: high_capital_requirement" in text
