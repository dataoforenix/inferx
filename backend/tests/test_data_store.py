from __future__ import annotations

import pandas as pd
import pytest

from app.data_store import REQUIRED_COLUMNS, SCHEMA_COLUMNS, DataValidationError, load_categories
from tests.conftest import TEST_CSV


def test_real_csv_loads_five_categories():
    store = load_categories(TEST_CSV)
    assert len(store.categories) == 5
    assert all(len(c.hs6) == 6 and c.hs6.isdigit() for c in store.list())
    assert all(c.name_ar and c.name_en for c in store.list())


def test_real_csv_placeholders_are_flagged():
    store = load_categories(TEST_CSV)
    placeholder_ids = [c.category_id for c in store.list() if c.data_status == "TODO_REAL_DATA"]
    for cid in placeholder_ids:
        assert any(w.startswith(cid) and "TODO_REAL_DATA" in w for w in store.warnings)


def test_real_csv_has_all_required_columns(csv_frame):
    assert set(REQUIRED_COLUMNS) <= set(csv_frame.columns)


def test_parsed_types(csv_frame, write_csv):
    store = load_categories(write_csv(csv_frame))
    rec = store.list()[0]
    assert isinstance(rec.local_factories, int)
    assert isinstance(rec.imports_usd[2024], float)
    assert rec.keywords_en and all(isinstance(k, str) for k in rec.keywords_en)


def test_hs6_leading_zeros_preserved(csv_frame, write_csv):
    csv_frame.loc[0, "hs6"] = "070200"
    store = load_categories(write_csv(csv_frame))
    assert store.list()[0].hs6 == "070200"


def test_missing_file(tmp_path):
    with pytest.raises(DataValidationError, match="file not found"):
        load_categories(tmp_path / "nope.csv")


def test_missing_column(csv_frame, write_csv):
    with pytest.raises(DataValidationError, match="missing columns: customs_pct"):
        load_categories(write_csv(csv_frame.drop(columns=["customs_pct"])))


def _with_rows(frame: pd.DataFrame, n: int) -> pd.DataFrame:
    """n valid rows: the fixture rows, repeated with fresh category ids if needed."""
    rows = [frame.iloc[i % len(frame)].copy() for i in range(n)]
    for i, row in enumerate(rows):
        row["category_id"] = f"cat_{i}"
    return pd.DataFrame(rows).reset_index(drop=True)


@pytest.mark.parametrize("n", [3, 5, 6, 20])
def test_category_count_within_limits_loads(csv_frame, write_csv, n):
    assert len(load_categories(write_csv(_with_rows(csv_frame, n))).categories) == n


@pytest.mark.parametrize("n", [2, 21])
def test_category_count_outside_limits_fails(csv_frame, write_csv, n):
    with pytest.raises(DataValidationError, match=f"between 3 and 20 categories, found {n}"):
        load_categories(write_csv(_with_rows(csv_frame, n)))


def test_minimum_count_is_configurable(csv_frame, write_csv):
    assert len(load_categories(write_csv(_with_rows(csv_frame, 1)), min_categories=1).categories) == 1


def test_duplicate_id(csv_frame, write_csv):
    csv_frame.loc[1, "category_id"] = csv_frame.loc[0, "category_id"]
    with pytest.raises(DataValidationError, match="duplicate category_id"):
        load_categories(write_csv(csv_frame))


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("hs6", "3924", "must be exactly 6 digits"),
        ("category_id", "Bad ID", "lowercase snake_case"),
        ("data_status", "REAL", "data_status must be one of"),
        ("name_en", "", "name_en is required"),
        ("customs_pct", "abc", "is not a number"),
        ("customs_pct", "-0.1", "outside"),
        ("machinery_availability", "7", "outside"),
        ("import_price_per_kg_usd", "0", "outside"),
        ("imports_2024_usd", "inf", "must be finite"),
        ("imports_2024_usd", "nan", "must be finite"),
        ("local_factories", "2.5", "whole number"),
        ("factories_saturation", "0", "outside"),
    ],
)
def test_invalid_values_rejected(csv_frame, write_csv, column, value, message):
    csv_frame.loc[0, column] = value
    with pytest.raises(DataValidationError, match=message):
        load_categories(write_csv(csv_frame))


def test_all_errors_reported_together(csv_frame, write_csv):
    csv_frame.loc[0, "hs6"] = "12"
    csv_frame.loc[3, "customs_pct"] = "x"
    with pytest.raises(DataValidationError) as exc:
        load_categories(write_csv(csv_frame))
    assert len(exc.value.errors) == 2


def test_empty_numeric_cell_becomes_none_with_warning(csv_frame, write_csv):
    csv_frame.loc[0, "local_cost_per_kg_est_usd"] = ""
    csv_frame.loc[0, "imports_2020_usd"] = ""
    store = load_categories(write_csv(csv_frame))
    rec = store.list()[0]
    assert rec.local_cost_per_kg_est_usd is None
    assert rec.imports_usd[2020] is None
    assert set(rec.missing_fields) == {"local_cost_per_kg_est_usd", "imports_2020_usd"}
    assert any("missing values" in w and rec.category_id in w for w in store.warnings)


def test_price_inconsistency_warns(csv_frame, write_csv):
    csv_frame.loc[0, "import_price_per_kg_usd"] = "99"
    store = load_categories(write_csv(csv_frame))
    assert any("differs from imports_2024/weight" in w for w in store.warnings)


def test_verified_row_has_no_placeholder_warning(csv_frame, write_csv):
    csv_frame["data_status"] = "VERIFIED"
    store = load_categories(write_csv(csv_frame))
    assert not any("TODO_REAL_DATA" in w for w in store.warnings)


def test_utf8_bom_is_accepted(csv_frame, tmp_path):
    path = tmp_path / "bom.csv"
    csv_frame.to_csv(path, index=False, encoding="utf-8-sig")
    assert len(load_categories(path).categories) == 5


def test_whitespace_is_trimmed(csv_frame, write_csv):
    csv_frame.loc[0, "category_id"] = "  " + csv_frame.loc[0, "category_id"] + " "
    csv_frame.loc[0, "customs_pct"] = " 0.2 "
    store = load_categories(write_csv(csv_frame))
    assert store.list()[0].customs_pct == 0.2


# --- optional columns (final schema) -----------------------------------------------

def test_optional_columns_default_to_empty(csv_frame, write_csv):
    rec = load_categories(write_csv(csv_frame)).list()[0]
    assert (rec.risk_notes, rec.competition_note, rec.source_url, rec.tariff_source_url) == ("", "", "", "")
    assert rec.estimated_fields == [] and rec.machine_cost_jod_min is None and rec.machine_cost_jod_max is None
    assert rec.missing_fields == []  # optional columns never lower completeness


def test_header_matches_final_schema_order(csv_frame):
    assert list(csv_frame.columns) == list(SCHEMA_COLUMNS)


def test_csv_without_optional_columns_still_loads(csv_frame, write_csv):
    old = csv_frame.drop(columns=["risk_notes", "machine_cost_jod_max", "estimated_fields"])
    store = load_categories(write_csv(old))
    assert len(store.categories) == 5
    assert any("optional columns not in the file" in w and "risk_notes" in w for w in store.warnings)


def test_optional_values_are_parsed(csv_frame, write_csv):
    csv_frame.loc[0, "risk_notes"] = "Resin prices rose 8.3% last year"
    csv_frame.loc[0, "source_url"] = "https://comtrade.un.org/data"
    csv_frame.loc[0, "tariff_source_url"] = "http://customs.gov.jo"
    csv_frame.loc[0, "estimated_fields"] = "local_cost_per_kg_est_usd; shipping_pct"
    csv_frame.loc[0, "machine_cost_jod_min"] = "15000"
    csv_frame.loc[0, "machine_cost_jod_max"] = "40000"
    rec = load_categories(write_csv(csv_frame)).list()[0]
    assert rec.risk_notes.startswith("Resin") and rec.source_url.startswith("https://")
    assert rec.estimated_fields == ["local_cost_per_kg_est_usd", "shipping_pct"]
    assert (rec.machine_cost_jod_min, rec.machine_cost_jod_max) == (15000.0, 40000.0)


def test_machine_cost_one_side_only_is_fine(csv_frame, write_csv):
    csv_frame.loc[0, "machine_cost_jod_max"] = "40000"
    assert load_categories(write_csv(csv_frame)).list()[0].machine_cost_jod_min is None


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"machine_cost_jod_min": "50000", "machine_cost_jod_max": "40000"}, "is less than machine_cost_jod_min"),
        ({"machine_cost_jod_min": "-1"}, "outside"),
        ({"machine_cost_jod_max": "lots"}, "is not a number"),
        ({"estimated_fields": "shipping_pct;profit_margin"}, "unknown column names: profit_margin"),
        ({"source_url": "comtrade.un.org"}, "must start with http:// or https://"),
        ({"tariff_source_url": "ftp://x"}, "must start with http:// or https://"),
    ],
)
def test_optional_column_validation(csv_frame, write_csv, changes, message):
    for col, value in changes.items():
        csv_frame.loc[0, col] = value
    with pytest.raises(DataValidationError, match=message):
        load_categories(write_csv(csv_frame))


# --- data/categories_template.csv (the file handed to the data team) ----------------

TEMPLATE_CSV = TEST_CSV.parent.parent.parent / "data" / "categories_template.csv"


def test_template_loads_with_minimum_one():
    store = load_categories(TEMPLATE_CSV, min_categories=1)
    assert store.ids == ["example_product"]
    rec = store.get("example_product")
    assert rec.data_status == "TODO_REAL_DATA" and rec.estimated_fields and rec.source_url.startswith("https://")


def test_template_header_is_the_final_schema():
    assert list(pd.read_csv(TEMPLATE_CSV, dtype=str, nrows=0).columns) == list(SCHEMA_COLUMNS)


def test_template_alone_is_not_a_valid_dataset():
    with pytest.raises(DataValidationError, match="between 3 and 20"):
        load_categories(TEMPLATE_CSV)


# --- cost build-up, landed price and USD machine-cost columns ------------------------------

def _rich(csv_frame, **values):
    """Row 0 (plastic_kitchenware: price 2.5, customs 0.20, local 1.90) with consistent optional values."""
    base = {
        "raw_material_price_usd_per_kg": "1.00", "material_kg_per_kg_product": "1.20",
        "conversion_cost_per_kg_usd": "0.70",  # 1.00 x 1.20 + 0.70 = 1.90 = local cost
        "protection_pct": "0.25", "landed_price_per_kg_usd": "3.00",  # 2.5 x 1.2
        "machine_cost_jod_min": "10000", "machine_cost_jod_max": "20000",
        "machine_cost_usd_min": "14104", "machine_cost_usd_max": "28208",
        "machine_source": "Supplier listings, Oct 2026: line USD 14,104-28,208",
        "machine_source_urls": "https://a.example/x ; https://b.example/y",
        "estimated_fields": "conversion_cost_per_kg_usd;protection_pct;material_kg_per_kg_product;"
                            "raw_material_price_usd_per_kg;machine_cost_usd_max;machine_source",
    }
    base.update(values)
    for col, value in base.items():
        csv_frame.loc[0, col] = value
    return csv_frame


def test_new_optional_columns_are_parsed(csv_frame, write_csv):
    store = load_categories(write_csv(_rich(csv_frame)))
    rec = store.list()[0]
    assert (rec.raw_material_price_usd_per_kg, rec.material_kg_per_kg_product, rec.conversion_cost_per_kg_usd) == (
        1.0, 1.2, 0.7)
    assert (rec.protection_pct, rec.landed_price_per_kg_usd) == (0.25, 3.0)
    assert (rec.machine_cost_usd_min, rec.machine_cost_usd_max) == (14104.0, 28208.0)
    assert rec.machine_source.startswith("Supplier") and rec.machine_source_urls == [
        "https://a.example/x", "https://b.example/y"]
    assert "machine_source" in rec.estimated_fields and rec.missing_fields == []
    assert not [w for w in store.warnings if "differs" in w]  # all consistent


def test_new_columns_empty_is_fine(csv_frame, write_csv):
    rec = load_categories(write_csv(csv_frame)).list()[0]
    assert rec.machine_cost_usd_max is None and rec.machine_source_urls == [] and rec.missing_fields == []


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"machine_cost_usd_min": "50000", "machine_cost_usd_max": "40000"}, "machine_cost_usd_max=40000.0 is less"),
        ({"raw_material_price_usd_per_kg": "-1"}, "outside"),
        ({"conversion_cost_per_kg_usd": "abc"}, "is not a number"),
        ({"protection_pct": "33"}, "outside"),
        ({"machine_source_urls": "https://ok.example ; www.bad.example"}, "links that don't start with http"),
    ],
)
def test_new_column_validation(csv_frame, write_csv, changes, message):
    with pytest.raises(DataValidationError, match=message):
        load_categories(write_csv(_rich(csv_frame, **changes)))


@pytest.mark.parametrize(
    ("changes", "warning"),
    [
        ({"machine_cost_jod_max": "20500"}, "machine_cost_jod_max=20500 x 1.4104"),  # 2.5% off
        ({"conversion_cost_per_kg_usd": "0.80"}, "local_cost_per_kg_est_usd=1.9 differs"),  # build 2.00, 5% off
        ({"landed_price_per_kg_usd": "3.10"}, "landed_price_per_kg_usd=3.1 differs"),  # 3.3% off
    ],
)
def test_consistency_warnings(csv_frame, write_csv, changes, warning):
    store = load_categories(write_csv(_rich(csv_frame, **changes)))  # warnings, never errors
    assert any(warning in w for w in store.warnings), store.warnings


@pytest.mark.parametrize(
    "changes",
    [
        {"machine_cost_jod_max": "20150"},  # 0.75% off: within 1%
        {"conversion_cost_per_kg_usd": "0.75"},  # build 1.95: 2.6% off, within 3%
        {"landed_price_per_kg_usd": "3.05"},  # 1.7% off: within 2%
    ],
)
def test_consistency_within_tolerance_is_quiet(csv_frame, write_csv, changes):
    store = load_categories(write_csv(_rich(csv_frame, **changes)))
    assert not [w for w in store.warnings if "differs" in w]


def test_jod_rate_is_defined_once():
    import app.data_store as ds

    assert ds.JOD_TO_USD == 1.4104
