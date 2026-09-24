import csv
from datetime import date

import pytest

from moneytrail.importers import detect_bank, parse_file
from moneytrail.importers.common import parse_amount, read_text
from moneytrail.store import Store
from moneytrail.synth import WRITERS, export, generate, load_catalog


@pytest.mark.parametrize(
    "text, cents",
    [("12,34", 1234), ("-12,34", -1234), ("+1.234,56", 123456), ("-12.34", -1234), ("1,234.56", 123456), ("0,99", 99)],
)
def test_parse_amount(text, cents):
    assert parse_amount(text) == cents


@pytest.fixture(scope="module")
def synth():
    return generate(months=4, end=date(2026, 4, 30), seed=3)


@pytest.mark.parametrize("bank", list(WRITERS))
def test_round_trip(bank, synth, tmp_path):
    path = export(synth, bank, tmp_path)
    assert detect_bank(read_text(path)) == bank

    txns = parse_file(path)
    with (tmp_path / "labels.csv").open(encoding="utf-8") as f:
        labels = list(csv.DictReader(f))

    assert len(txns) == len(synth) == len(labels)
    assert sum(t.amount_cents for t in txns) == sum(t.amount_cents for t in synth)
    assert [t.kind for t in txns] == [row["kind"] for row in labels]
    assert len({t.txn_id for t in txns}) == len(txns)


@pytest.mark.parametrize("bank", list(WRITERS))
def test_heldout_catalogue_round_trips(bank, tmp_path):
    catalog = load_catalog("heldout")
    txns = generate(months=4, end=date(2026, 4, 30), seed=3, catalog=catalog)
    parsed = parse_file(export(txns, bank, tmp_path, catalog=catalog))
    assert len(parsed) == len(txns)
    assert sum(t.amount_cents for t in parsed) == sum(t.amount_cents for t in txns)


def test_abnamro_description_is_unpacked(synth, tmp_path):
    txns = parse_file(export(synth, "abnamro", tmp_path))
    by_kind = {t.kind: t for t in txns}
    assert by_kind["card"].counterparty and "," not in by_kind["card"].counterparty
    assert by_kind["direct_debit"].counterparty_iban.startswith("NL")
    assert "Naam:" not in by_kind["direct_debit"].description


def test_reimport_and_overlap_are_deduplicated(tmp_path):
    full = generate(months=4, end=date(2026, 4, 30), seed=3)
    early = [t for t in full if t.booked < date(2026, 3, 15)]
    late = [t for t in full if t.booked >= date(2026, 2, 1)]

    store = Store()
    store.add(parse_file(export(full, "ing", tmp_path / "full")))
    assert store.add(parse_file(export(full, "ing", tmp_path / "again"))) == 0

    store = Store()
    store.add(parse_file(export(early, "ing", tmp_path / "early")))
    store.add(parse_file(export(late, "ing", tmp_path / "late")))
    assert store.count() == len(full)
