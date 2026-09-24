from datetime import date

import pytest

from moneytrail.merchants import display_name, normalize, resolve, similar
from moneytrail.model import Transaction


@pytest.mark.parametrize(
    "raw, key",
    [
        ("AH 1234 UTRECHT", "ah"),
        ("SumUp  *Bakkerij Jansen", "bakkerij jansen"),
        ("CCV*BAKKERIJ JANSEN", "bakkerij jansen"),
        ("NS GROEP IZ NS REIZIGERS", "ns reizigers"),
        ("AAB INZ TIKKIE", "tikkie"),
        ("Stichting Derdengelden bol.com", "bol"),
        ("Netflix International B.V.", "netflix"),
        ("Spotify P2F7A3C9D1", "spotify"),
        ("Spotify AB", "spotify"),
        ("Thuisbezorgd.nl via Takeaway.com", "thuisbezorgd"),
        ("JUMBO DEN HAAG 4411", "jumbo"),
    ],
)
def test_normalize(raw, key):
    assert normalize(raw) == key


@pytest.mark.parametrize(
    "a, b",
    [("ah", "albert heijn"), ("thuisbez", "thuisbezorgd"), ("jumbo", "jumbo supermarkten"), ("la piazza", "restaurant la piazza")],
)
def test_similar(a, b):
    assert similar(a, b)


@pytest.mark.parametrize(
    "a, b",
    [("l jansen", "bakkerij jansen"), ("restaurant la piazza", "restaurant de zaak"), ("jumbo", "lidl"), ("t mobile", "odido")],
)
def test_not_similar(a, b):
    assert not similar(a, b)


def test_display_name():
    assert display_name("ALBERT HEIJN 1234") == "Albert Heijn"
    assert display_name("Albert Heijn 4321 Utre") == "Albert Heijn"  # truncated by the terminal
    assert display_name("bol.com") == "bol.com"
    assert display_name("CCV*BAKKERIJ JANSEN") == "Bakkerij Jansen"
    assert display_name("KOFFIEBAR DE STOEP") == "Koffiebar De Stoep"
    assert display_name("APPLE.COM/BILL") == "Apple Bill"
    assert display_name("ANWB B.V.") == "ANWB"
    assert display_name("NS Reizigers") == "NS Reizigers"


def _txn(i: int, counterparty: str, iban: str = "") -> Transaction:
    return Transaction(f"t{i}", "ing", "NL00", date(2026, 1, 1), -100, "card", counterparty, iban, "", "x", i)


def test_shared_iban_merges_renamed_company():
    res = resolve([_txn(1, "T-Mobile Netherlands B.V.", "NL01X"), _txn(2, "Odido Netherlands B.V.", "NL01X")])
    assert len(res.merchants) == 1


def test_rename_shows_the_new_name():
    txns = [
        Transaction(f"t{i}", "ing", "NL00", date(2026, 1 + i, 22), -2000, "direct_debit",
                    "T-Mobile Netherlands B.V." if i < 4 else "Odido Netherlands B.V.", "NL01X", "", "x", i)
        for i in range(8)
    ]
    assert [m.name for m in resolve(txns).merchants.values()] == ["Odido"]


def test_interleaved_variants_are_not_a_rename():
    names = ["AH 1234 UTRECHT", "Albert Heijn 1234", "AH 1234 UTRECHT", "Albert Heijn 1234"] * 2
    txns = [
        Transaction(f"t{i}", "ing", "NL00", date(2026, 1 + i, 1), -500, "card", n, "", "", "x", i)
        for i, n in enumerate(names)
    ]
    assert [m.name for m in resolve(txns).merchants.values()] == ["Albert Heijn"]


def test_resolve_prefers_the_full_name():
    names = ["AH 1234 UTRECHT", "AH 1234 UTRECHT", "ALBERT HEIJN 5521", "Albert Heijn 5521 Utrecht"]
    res = resolve([_txn(i, n) for i, n in enumerate(names)])
    assert [m.name for m in res.merchants.values()] == ["Albert Heijn"]
