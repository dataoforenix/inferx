"""scripts/refresh_trade_data.py on the frozen fixture CSV. Comtrade is always faked (no network)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from urllib.parse import parse_qs, urlparse

import pytest

import app.comtrade as comtrade_module
from app.comtrade import ComtradeClient, TradeSeries
from app.data_store import inspect_categories
from scripts.refresh_trade_data import TRADE_COLUMNS, main
from tests.conftest import TEST_CSV


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


ROWS = read(TEST_CSV)
FIRST, SECOND = ROWS[0], ROWS[1]


def scaled(row, factor, weight_factor=1.0):
    return TradeSeries(
        hs6=row["hs6"],
        imports_usd={y: float(row[f"imports_{y}_usd"]) * factor for y in range(2020, 2025)},
        import_weight_kg_2024=float(row["import_weight_kg_2024"]) * weight_factor,
    )


class FakeClient:
    def __init__(self, by_hs6):
        self.by_hs6 = by_hs6
        self.calls = []

    def fetch(self, hs6):
        self.calls.append(hs6)
        return self.by_hs6.get(hs6)


@pytest.fixture
def paths(tmp_path):
    src = tmp_path / "categories.csv"
    src.write_bytes(TEST_CSV.read_bytes())
    return src, tmp_path / "categories.refreshed.csv"


def run(paths, client):
    src, out = paths
    return main(["--csv", str(src), "--out", str(out)], client=client)


def test_only_trade_columns_change_and_original_is_untouched(paths, capsys):
    src, out = paths
    before = hashlib.sha256(src.read_bytes()).hexdigest()
    client = FakeClient({r["hs6"]: scaled(r, 1.02) for r in ROWS})
    assert run(paths, client) == 0
    assert hashlib.sha256(src.read_bytes()).hexdigest() == before
    old, new = read(src), read(out)
    assert list(new[0]) == list(old[0])  # same header, same order
    for o, n in zip(old, new):
        for column in o:
            if column in TRADE_COLUMNS:
                assert n[column] == str(round(float(o[column]) * (1.02 if column.startswith("imports") else 1)))
            else:
                assert n[column] == o[column], column
    assert client.calls == [r["hs6"] for r in ROWS]


def test_refreshed_file_still_loads(paths):
    run(paths, FakeClient({r["hs6"]: scaled(r, 1.02) for r in ROWS}))
    assert inspect_categories(paths[1]).errors == []


def test_changes_over_5_percent_are_flagged(paths, capsys):
    client = FakeClient({FIRST["hs6"]: scaled(FIRST, 1.10), SECOND["hs6"]: scaled(SECOND, 1.01)})
    run(paths, client)
    out = capsys.readouterr().out
    first_lines = [l for l in out.splitlines() if l.startswith(FIRST["category_id"] + " ") and "imports_" in l]
    second_lines = [l for l in out.splitlines() if l.startswith(SECOND["category_id"] + " ") and "imports_" in l]
    assert first_lines and all("+10.0%" in l and "over 5%" in l for l in first_lines)
    assert second_lines and not any("over 5%" in l for l in second_lines)
    assert "source_notes" in out and "check_data.py" in out


def test_values_not_returned_keep_the_old_value(paths, capsys):
    partial = scaled(FIRST, 1.5)
    partial = TradeSeries(partial.hs6, {**partial.imports_usd, 2021: None}, None)
    assert run(paths, FakeClient({FIRST["hs6"]: partial})) == 2  # other categories failed entirely
    new = {r["category_id"]: r for r in read(paths[1])}
    first = new[FIRST["category_id"]]
    assert first["imports_2021_usd"] == FIRST["imports_2021_usd"]
    assert first["import_weight_kg_2024"] == FIRST["import_weight_kg_2024"]
    assert first["imports_2024_usd"] == str(round(float(FIRST["imports_2024_usd"]) * 1.5))
    assert new[SECOND["category_id"]] == SECOND
    assert "not returned: kept" in capsys.readouterr().out


def test_nothing_returned_writes_nothing(paths):
    assert run(paths, FakeClient({})) == 1
    assert not paths[1].exists()


def test_refuses_to_overwrite_the_input(paths):
    src, _ = paths
    before = src.read_bytes()
    assert main(["--csv", str(src), "--out", str(src)], client=FakeClient({})) == 1
    assert src.read_bytes() == before


def test_end_to_end_with_mocked_http(paths, monkeypatch):
    """The real ComtradeClient, with urlopen and time faked: every category's hs6 is requested for each year."""
    now = [0.0]
    urls = []

    def fake_urlopen(request, timeout):
        urls.append(request.full_url)
        q = parse_qs(urlparse(request.full_url).query)
        year, hs6 = int(q["period"][0]), q["cmdCode"][0]
        row = next(r for r in ROWS if r["hs6"] == hs6)
        body = {"data": [{"primaryValue": float(row[f"imports_{year}_usd"]),
                          "netWgt": float(row["import_weight_kg_2024"])}]}
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr(comtrade_module, "urlopen", fake_urlopen)
    client = ComtradeClient(min_interval=5.0, total_timeout=90.0, cache_ttl=0,
                            clock=lambda: now[0], sleep=lambda s: now.__setitem__(0, now[0] + s))
    assert run(paths, client) == 0
    assert len(urls) == 5 * len(ROWS)
    for old, new in zip(read(paths[0]), read(paths[1])):  # same figures came back: unchanged (to the whole unit)
        for column in TRADE_COLUMNS:
            assert float(new[column]) == pytest.approx(float(old[column]), abs=0.5)
