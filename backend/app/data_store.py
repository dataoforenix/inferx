"""Load and validate categories.csv.

Two entry points share one set of checks:
- inspect_categories() never raises. It collects every problem as an Issue (row, column,
  value, message and a plain-language fix). scripts/check_data.py uses it with detailed=True,
  which adds heuristic warnings (suspicious jumps, JOD-vs-USD hints, disabled score components).
- load_categories() is what the app uses: it raises DataValidationError on any error, so the
  app refuses to start on bad data, and returns a DataStore with the loader warnings.

Empty numeric cells are allowed: they become None and are reported as warnings, so scoring
can lower data completeness instead of guessing.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pandas as pd

from app.schemas import IMPORT_YEARS, CategoryRecord

MIN_CATEGORIES = 3
MAX_CATEGORIES = 20
PRICE_CONSISTENCY_TOLERANCE = 0.05
JOD_TO_USD = 1.4104  # CBJ peg (1 USD = 0.709 JOD). The only place this rate is defined.
MACHINE_COST_FX_TOLERANCE = 0.01  # machine_cost_jod_* x rate vs machine_cost_usd_*
LOCAL_COST_BUILD_TOLERANCE = 0.03  # local cost vs raw material x ratio + conversion
LANDED_PRICE_TOLERANCE = 0.02  # landed_price_per_kg_usd vs import price x (1 + customs)
SUSPICIOUS_JUMP = 10  # a year 10x (or 1/10) its neighbours is probably a units mistake

TEXT_COLUMNS = (
    "category_id", "name_en", "name_ar", "description_en", "keywords_en", "keywords_ar",
    "hs6", "machinery", "raw_materials", "data_status", "source_notes",
)
REQUIRED_TEXT = ("category_id", "name_en", "name_ar", "description_en", "hs6", "data_status")

# column -> (min, max, integer?). Bounds are inclusive.
NUMERIC_RULES: dict[str, tuple[float, float, bool]] = {
    **{f"imports_{y}_usd": (0, 1e12, False) for y in IMPORT_YEARS},
    "import_weight_kg_2024": (1e-9, 1e12, False),
    "import_price_per_kg_usd": (1e-9, 1e6, False),
    "shipping_pct": (0, 2, False),
    "customs_pct": (0, 2, False),
    "local_cost_per_kg_est_usd": (1e-9, 1e6, False),
    "machinery_availability": (0, 5, False),
    "raw_material_local": (0, 5, False),
    "skills_availability": (0, 5, False),
    "local_factories": (0, 100_000, True),
    "factories_saturation": (1, 100_000, True),
}

REQUIRED_COLUMNS = TEXT_COLUMNS + tuple(NUMERIC_RULES)

# Optional columns (appended at the end of the header). Cells may be empty; a CSV without
# these columns still loads, with a warning.
OPTIONAL_TEXT_COLUMNS = (
    "risk_notes", "competition_note", "source_url", "tariff_source_url", "estimated_fields",
    "machine_source", "machine_source_urls",
)
OPTIONAL_NUMERIC_RULES: dict[str, tuple[float, float, bool]] = {
    "machine_cost_jod_min": (0, 1e10, False),
    "machine_cost_jod_max": (0, 1e10, False),
    # Cost build-up: local cost = raw material price x kg of material per kg + conversion cost.
    "raw_material_price_usd_per_kg": (0, 1e6, False),
    "material_kg_per_kg_product": (0, 1e6, False),
    "conversion_cost_per_kg_usd": (0, 1e6, False),
    "protection_pct": (0, 2, False),  # fraction, like shipping_pct / customs_pct
    "landed_price_per_kg_usd": (0, 1e6, False),
    # Equipment cost in USD (canonical; machine_cost_jod_* are kept for older files).
    "machine_cost_usd_min": (0, 1e10, False),
    "machine_cost_usd_max": (0, 1e10, False),
}
URL_COLUMNS = ("source_url", "tariff_source_url")
URL_LIST_COLUMNS = ("machine_source_urls",)

# The final header, in order. The template and the data checker use this.
SCHEMA_COLUMNS = (
    "category_id", "name_en", "name_ar", "description_en", "keywords_en", "keywords_ar", "hs6",
    *(f"imports_{y}_usd" for y in IMPORT_YEARS),
    "import_weight_kg_2024", "import_price_per_kg_usd", "shipping_pct", "customs_pct",
    "local_cost_per_kg_est_usd", "machinery_availability", "raw_material_local", "skills_availability",
    "local_factories", "factories_saturation", "machinery", "raw_materials", "data_status", "source_notes",
    "risk_notes", "competition_note", "source_url", "tariff_source_url", "estimated_fields",
    "machine_cost_jod_min", "machine_cost_jod_max",
    "raw_material_price_usd_per_kg", "material_kg_per_kg_product", "conversion_cost_per_kg_usd",
    "protection_pct", "landed_price_per_kg_usd", "machine_cost_usd_min", "machine_cost_usd_max",
    "machine_source", "machine_source_urls",
)
assert set(SCHEMA_COLUMNS) == set(REQUIRED_COLUMNS) | set(OPTIONAL_TEXT_COLUMNS) | set(OPTIONAL_NUMERIC_RULES)

# Which empty cells switch off which score component (mirrors app/scoring.py).
COMPONENT_INPUTS = {
    "market": (f"imports_{IMPORT_YEARS[-1]}_usd",),
    "market trend": (f"imports_{IMPORT_YEARS[0]}_usd",),
    "cost": ("import_price_per_kg_usd", "customs_pct", "local_cost_per_kg_est_usd"),  # shipping: info only
    "feasibility": ("machinery_availability", "raw_material_local", "skills_availability"),
    "competition": ("local_factories", "factories_saturation"),
}

PCT_COLUMNS = ("shipping_pct", "customs_pct", "protection_pct")
RATING_COLUMNS = ("machinery_availability", "raw_material_local", "skills_availability")
VALID_STATUSES = {"VERIFIED", "ESTIMATE", "TODO_REAL_DATA"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
HS6_PATTERN = re.compile(r"^\d{6}$")
TEMPLATE_HINT = "copy the header from data/categories_template.csv"


class DataValidationError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("categories.csv is invalid:\n  - " + "\n  - ".join(errors))


@dataclass(frozen=True)
class Issue:
    level: Literal["error", "warning"]
    message: str
    row: int | None = None  # spreadsheet row number (header is row 1)
    category_id: str = ""
    column: str = ""
    value: str = ""
    fix: str = ""
    detailed_only: bool = False  # heuristic: reported by check_data.py, not by the app

    @property
    def text(self) -> str:
        """The loader's message format (unchanged from earlier versions)."""
        if self.row is None:
            return self.message
        if self.level == "error":
            return f"row {self.row} ({self.category_id or '?'}): {self.message}"
        return f"{self.category_id}: {self.message}"


@dataclass
class Inspection:
    records: dict[str, CategoryRecord]
    issues: list[Issue]
    row_count: int = 0
    columns: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]


@dataclass
class DataStore:
    categories: dict[str, CategoryRecord]
    warnings: list[str] = field(default_factory=list)

    def get(self, category_id: str) -> CategoryRecord | None:
        return self.categories.get(category_id)

    def list(self) -> list[CategoryRecord]:
        return list(self.categories.values())

    @property
    def ids(self) -> list[str]:
        return list(self.categories)


def _split(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(";") if part.strip()]


def _is_url(value: str) -> bool:
    return value.lower().startswith(("http://", "https://"))


def _differs(a: float, b: float, tolerance: float) -> bool:
    """Relative difference of a against reference b above tolerance."""
    return b != 0 and abs(a - b) / abs(b) > tolerance


def _fmt_bound(x: float) -> str:
    return "0" if x < 1e-6 else f"{x:g}"


def _number_fix(column: str, raw: str, value: float | None, rule: tuple[float, float, bool]) -> str:
    lo, hi, _ = rule
    if value is None:
        if "%" in raw:
            return "Remove the % sign and write a fraction (25% -> 0.25)."
        if "," in raw:
            return "Remove thousands separators: write 1250000, not 1,250,000."
        return "Write a plain number (digits and an optional decimal point), or leave the cell empty if unknown."
    if column in PCT_COLUMNS and value > hi:
        return f"Looks like {raw} instead of {value / 100:g}: write fractions, not percentages (0.25 = 25%)."
    if column in RATING_COLUMNS:
        return "Ratings use a 0 to 5 scale (0 = not available in Jordan, 5 = fully available)."
    if column == "factories_saturation":
        return "Saturation must be at least 1 (the factory count at which the market is full)."
    if lo > 0 and value <= 0:
        return "This value must be greater than 0; leave the cell empty if unknown."
    return f"Use a value between {_fmt_bound(lo)} and {_fmt_bound(hi)}."


def _parse_number(raw, column, rule, where_row, cid, issues):
    if raw == "":
        return None
    lo, hi, is_int = rule

    def error(message, value=None):
        issues.append(Issue("error", message, where_row, cid, column, raw, _number_fix(column, raw, value, rule)))

    try:
        value = float(raw)
    except ValueError:
        error(f"{column}={raw!r} is not a number")
        return None
    if not math.isfinite(value):
        issues.append(Issue("error", f"{column} must be finite", where_row, cid, column, raw,
                            "Write a real number, or leave the cell empty if unknown."))
        return None
    if not lo <= value <= hi:
        error(f"{column}={value} is outside [{lo}, {hi}]", value)
        return None
    if is_int:
        if value != int(value):
            issues.append(Issue("error", f"{column}={value} must be a whole number", where_row, cid, column, raw,
                                "Write a whole number (no decimals)."))
            return None
        return int(value)
    return value


def _hs6_fix(raw: str) -> str:
    if raw.isdigit() and len(raw) == 5:
        return f"Looks like Excel stripped a leading zero: write 0{raw} and format the hs6 column as Text."
    if re.fullmatch(r"\d{5,6}\.0+", raw):
        return "Excel turned the code into a number: format the hs6 column as Text and type the 6 digits."
    return "Write exactly 6 digits (the HS6 code), formatted as Text."


def inspect_categories(
    path: Path, min_categories: int = MIN_CATEGORIES, max_categories: int = MAX_CATEGORIES, detailed: bool = False,
) -> Inspection:
    """Validate the CSV and collect every issue. Never raises for data problems."""
    issues: list[Issue] = []
    if not path.exists():
        return Inspection({}, [Issue("error", f"file not found: {path}", fix="Check the path.")])

    # Read everything as text so HS codes keep leading zeros and we control parsing.
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return Inspection({}, [Issue("error", "file is not UTF-8",
                                     fix="Save the file as 'CSV UTF-8' (Excel: File > Save As > CSV UTF-8).")])
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        return Inspection({}, [Issue("error", f"file is not a readable CSV: {exc}", fix="Re-export it as CSV.")])
    df.columns = [c.strip() for c in df.columns]
    columns = list(df.columns)

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        issues.append(Issue("error", f"missing columns: {', '.join(missing_cols)}", column=", ".join(missing_cols),
                            fix=f"Add the missing columns to the header ({TEMPLATE_HINT})."))
    absent_optional = [c for c in (*OPTIONAL_TEXT_COLUMNS, *OPTIONAL_NUMERIC_RULES) if c not in df.columns]
    if absent_optional:
        issues.append(Issue("warning", f"optional columns not in the file (treated as empty): "
                                       f"{', '.join(absent_optional)}", column=", ".join(absent_optional),
                            fix=f"Optional, but recommended: {TEMPLATE_HINT}."))
    for col in (*missing_cols, *absent_optional):
        df[col] = ""
    if detailed:
        unknown_cols = [c for c in columns if c not in SCHEMA_COLUMNS]
        if unknown_cols:
            issues.append(Issue("warning", f"unknown columns are ignored: {', '.join(unknown_cols)}",
                                column=", ".join(unknown_cols), fix="Check the spelling against the template.",
                                detailed_only=True))

    if not min_categories <= len(df) <= max_categories:
        issues.append(Issue("error", f"expected between {min_categories} and {max_categories} categories, "
                                     f"found {len(df)}",
                            fix=f"Provide {min_categories} to {max_categories} rows, one per category."))

    records: dict[str, CategoryRecord] = {}
    seen_ids: set[str] = set()
    rules = {**NUMERIC_RULES, **OPTIONAL_NUMERIC_RULES}
    for idx, raw_row in df.iterrows():
        row = {k: (v.strip() if isinstance(v, str) else "") for k, v in raw_row.items()}
        cid = row["category_id"]
        n = idx + 2  # +2: header line and 1-based
        row_issues: list[Issue] = []

        def err(message, column="", fix=""):
            row_issues.append(Issue("error", message, n, cid, column, row.get(column, ""), fix))

        for col in REQUIRED_TEXT:
            if col not in missing_cols and not row[col]:
                err(f"{col} is required", col, f"Fill in {col}; it cannot be empty.")
        if cid and not ID_PATTERN.match(cid):
            err("category_id must be lowercase snake_case", "category_id",
                "Use lowercase letters, digits and underscores, starting with a letter (e.g. plastic_buckets).")
        if cid and cid in seen_ids:
            err(f"duplicate category_id {cid!r}", "category_id", "Each category_id must be unique; rename one row.")
        seen_ids.add(cid)
        if row["hs6"] and not HS6_PATTERN.match(row["hs6"]):
            err(f"hs6={row['hs6']!r} must be exactly 6 digits", "hs6", _hs6_fix(row["hs6"]))
        if row["data_status"] and row["data_status"] not in VALID_STATUSES:
            err(f"data_status must be one of {sorted(VALID_STATUSES)}", "data_status",
                "Use VERIFIED, ESTIMATE or TODO_REAL_DATA.")

        nums = {col: _parse_number(row[col], col, rule, n, cid, row_issues) for col, rule in rules.items()}

        for unit in ("jod", "usd"):
            lo, hi = nums[f"machine_cost_{unit}_min"], nums[f"machine_cost_{unit}_max"]
            if lo is not None and hi is not None and hi < lo:
                err(f"machine_cost_{unit}_max={hi} is less than machine_cost_{unit}_min={lo}",
                    f"machine_cost_{unit}_max",
                    "The maximum must be at least the minimum: swap the two values or fix the typo.")
        estimated = _split(row["estimated_fields"])
        unknown = [name for name in estimated if name not in SCHEMA_COLUMNS]
        if unknown:
            err(f"estimated_fields has unknown column names: {', '.join(unknown)}", "estimated_fields",
                "List exact column names from the header, separated by ';'.")
        for col in URL_COLUMNS:
            if row[col] and not _is_url(row[col]):
                err(f"{col}={row[col]!r} must start with http:// or https://", col,
                    "Paste the full link, starting with https://.")
        url_lists = {col: _split(row[col]) for col in URL_LIST_COLUMNS}
        for col, urls in url_lists.items():
            bad = [u for u in urls if not _is_url(u)]
            if bad:
                err(f"{col} has links that don't start with http:// or https://: {', '.join(bad)}", col,
                    "Separate links with ';' and start each one with https://.")

        issues.extend(row_issues)
        if any(i.level == "error" for i in row_issues):
            continue  # don't build a record from a row we already know is bad

        record = CategoryRecord(
            category_id=cid,
            name_en=row["name_en"],
            name_ar=row["name_ar"],
            description_en=row["description_en"],
            keywords_en=_split(row["keywords_en"]),
            keywords_ar=_split(row["keywords_ar"]),
            hs6=row["hs6"],
            imports_usd={y: nums[f"imports_{y}_usd"] for y in IMPORT_YEARS},
            import_weight_kg_2024=nums["import_weight_kg_2024"],
            import_price_per_kg_usd=nums["import_price_per_kg_usd"],
            shipping_pct=nums["shipping_pct"],
            customs_pct=nums["customs_pct"],
            local_cost_per_kg_est_usd=nums["local_cost_per_kg_est_usd"],
            machinery_availability=nums["machinery_availability"],
            raw_material_local=nums["raw_material_local"],
            skills_availability=nums["skills_availability"],
            local_factories=nums["local_factories"],
            factories_saturation=nums["factories_saturation"],
            machinery=row["machinery"],
            raw_materials=row["raw_materials"],
            data_status=row["data_status"],
            source_notes=row["source_notes"],
            risk_notes=row["risk_notes"],
            competition_note=row["competition_note"],
            source_url=row["source_url"],
            tariff_source_url=row["tariff_source_url"],
            estimated_fields=estimated,
            machine_cost_jod_min=nums["machine_cost_jod_min"],
            machine_cost_jod_max=nums["machine_cost_jod_max"],
            raw_material_price_usd_per_kg=nums["raw_material_price_usd_per_kg"],
            material_kg_per_kg_product=nums["material_kg_per_kg_product"],
            conversion_cost_per_kg_usd=nums["conversion_cost_per_kg_usd"],
            protection_pct=nums["protection_pct"],
            landed_price_per_kg_usd=nums["landed_price_per_kg_usd"],
            machine_cost_usd_min=nums["machine_cost_usd_min"],
            machine_cost_usd_max=nums["machine_cost_usd_max"],
            machine_source=row["machine_source"],
            machine_source_urls=url_lists["machine_source_urls"],
        )
        records[cid] = record
        issues.extend(_record_warnings(record, n, detailed))

    return Inspection(records, issues, row_count=len(df), columns=columns)


def _record_warnings(record: CategoryRecord, n: int, detailed: bool) -> list[Issue]:
    cid = record.category_id
    out: list[Issue] = []

    def warn(message, column="", value="", fix="", detailed_only=False):
        out.append(Issue("warning", message, n, cid, column, value, fix, detailed_only))

    if record.data_status == "TODO_REAL_DATA":
        warn("values are TODO_REAL_DATA placeholders, not real trade statistics", "data_status",
             record.data_status, "Replace with real figures, then set data_status to ESTIMATE or VERIFIED.")
    if record.missing_fields:
        warn(f"missing values for {', '.join(record.missing_fields)}", ", ".join(record.missing_fields), "",
             "Fill them in if known; otherwise leave them empty (never guess).")

    value, weight, price = record.imports_usd[IMPORT_YEARS[-1]], record.import_weight_kg_2024, \
        record.import_price_per_kg_usd
    if value and weight and price:
        derived = value / weight
        if abs(derived - price) / derived > PRICE_CONSISTENCY_TOLERANCE:
            ratio = price / derived
            fix = "import_price_per_kg_usd should equal imports_2024_usd / import_weight_kg_2024 (within 5%)."
            if any(abs(ratio - r) / r < 0.05 for r in (JOD_TO_USD, 1 / JOD_TO_USD)):
                fix += " The gap is about the JOD/USD rate: one of the values may still be in JOD."
            warn(f"import_price_per_kg_usd={price} differs from imports_2024/weight={derived:.2f} by more than 5%",
                 "import_price_per_kg_usd", f"{price:g}", fix)

    # Consistency of the optional cost columns (warnings: the CSV numbers are never changed).
    for side in ("min", "max"):
        jod, usd = getattr(record, f"machine_cost_jod_{side}"), getattr(record, f"machine_cost_usd_{side}")
        if jod is not None and usd is not None and _differs(jod * JOD_TO_USD, usd, MACHINE_COST_FX_TOLERANCE):
            warn(f"machine_cost_jod_{side}={jod:g} x {JOD_TO_USD} = {jod * JOD_TO_USD:,.0f} USD differs from "
                 f"machine_cost_usd_{side}={usd:,.0f} by more than {MACHINE_COST_FX_TOLERANCE:.0%}",
                 f"machine_cost_jod_{side}", f"{jod:g}",
                 f"machine_cost_usd_{side} is the one used; fix the JOD value or leave it empty.")

    rm, ratio, conv, local = (record.raw_material_price_usd_per_kg, record.material_kg_per_kg_product,
                              record.conversion_cost_per_kg_usd, record.local_cost_per_kg_est_usd)
    if None not in (rm, ratio, conv, local):
        build = rm * ratio + conv
        if _differs(local, build, LOCAL_COST_BUILD_TOLERANCE):
            warn(f"local_cost_per_kg_est_usd={local:g} differs from raw_material_price_usd_per_kg x "
                 f"material_kg_per_kg_product + conversion_cost_per_kg_usd = {build:.3f} by more than "
                 f"{LOCAL_COST_BUILD_TOLERANCE:.0%}", "local_cost_per_kg_est_usd", f"{local:g}",
                 "Recompute the local cost from its build-up, or correct the build-up columns.")

    landed, price, customs = record.landed_price_per_kg_usd, record.import_price_per_kg_usd, record.customs_pct
    if None not in (landed, price, customs):
        expected = price * (1 + customs)
        if _differs(landed, expected, LANDED_PRICE_TOLERANCE):
            warn(f"landed_price_per_kg_usd={landed:g} differs from import_price_per_kg_usd x (1 + customs_pct) "
                 f"= {expected:.3f} by more than {LANDED_PRICE_TOLERANCE:.0%}", "landed_price_per_kg_usd",
                 f"{landed:g}", "Landed price = CIF import price x (1 + customs); freight is already in the CIF price.")

    if not detailed:
        return out

    # Heuristics for the data checker only.
    for component, cols in COMPONENT_INPUTS.items():
        empty = [c for c in cols if c in record.missing_fields]
        if empty:
            effect = ("growth trend is skipped; market uses import volume only" if component == "market trend"
                      else f"the {component} score is switched off and completeness drops")
            warn(f"empty {', '.join(empty)}: {effect}", ", ".join(empty), "",
                 "Fill these in if the numbers are known.", detailed_only=True)

    years = [(y, record.imports_usd[y]) for y in IMPORT_YEARS]
    for i, (year, v) in enumerate(years):
        neighbours = [nv for _, nv in years[max(0, i - 1):i] + years[i + 1:i + 2] if nv]
        if v and neighbours and all(v >= SUSPICIOUS_JUMP * nv or v * SUSPICIOUS_JUMP <= nv for nv in neighbours):
            warn(f"imports_{year}_usd is {SUSPICIOUS_JUMP}x away from its neighbouring years",
                 f"imports_{year}_usd", f"{v:g}",
                 "Check the units (USD vs JOD, thousands vs units) and the year.", detailed_only=True)

    if (record.local_factories is not None and record.factories_saturation is not None
            and record.local_factories > record.factories_saturation):
        warn(f"local_factories={record.local_factories} is above factories_saturation="
             f"{record.factories_saturation} (competition score will be 0)", "local_factories",
             str(record.local_factories), "Check both numbers; saturation is the count at which the market is full.",
             detailed_only=True)
    return out


def load_categories(
    path: Path, min_categories: int = MIN_CATEGORIES, max_categories: int = MAX_CATEGORIES
) -> DataStore:
    """Load the CSV for the app. Raises DataValidationError listing every error."""
    result = inspect_categories(path, min_categories, max_categories)
    if result.errors:
        raise DataValidationError([i.text for i in result.errors])
    return DataStore(categories=result.records, warnings=[i.text for i in result.warnings])
