from datetime import date, timedelta

from moneytrail.merchants import resolve
from moneytrail.model import Transaction
from moneytrail.recurring import detect

AS_OF = date(2026, 8, 31)


def _txns(name: str, dates: list[date], amounts: list[int], kind: str = "direct_debit", start: int = 0):
    return [
        Transaction(f"{name}{start + i}", "ing", "NL00", d, a, kind, name, "", "", "x", start + i)
        for i, (d, a) in enumerate(zip(dates, amounts))
    ]


def _monthly(n: int, day: int = 3, first=(2025, 3)) -> list[date]:
    y, m = first
    out = []
    for _ in range(n):
        out.append(date(y, m, day))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _detect(txns):
    return detect(txns, resolve(txns), as_of=AS_OF)


def test_monthly_with_price_rise():
    dates = _monthly(18)
    [s] = _detect(_txns("Netflix", dates, [-1399] * 8 + [-1599] * 10))
    assert s.cadence.name == "monthly" and s.status == "active"
    assert [(c.old_cents, c.new_cents) for c in s.price_changes] == [(-1399, -1599)]


def test_small_rent_rise_is_a_price_change():
    [s] = _detect(_txns("Mitros", _monthly(18, day=1), [-115000] * 10 + [-118500] * 8, kind="transfer_out"))
    assert len(s.price_changes) == 1


def test_one_off_amount_is_not_a_price_change():
    [s] = _detect(_txns("Ziggo", _monthly(12), [-5250] * 5 + [-7100] + [-5250] * 6))
    assert s.price_changes == []


def test_four_weekly_is_not_monthly():
    dates = [date(2025, 5, 5) + timedelta(days=28 * i) for i in range(16)]
    [s] = _detect(_txns("Basic-Fit", dates, [-2999] * 16))
    assert s.cadence.name == "four_weekly"


def test_cancelled_subscription():
    [s] = _detect(_txns("Disney Plus", _monthly(6), [-999] * 6))
    assert s.status == "stopped" and s.next_expected is None


def test_subscription_hidden_among_purchases():
    fees = _txns("NS Reizigers", _monthly(12, day=12), [-560] * 12)
    tickets = _txns("NS Reizigers", [date(2025, 3, 1) + timedelta(days=9 * i) for i in range(40)],
                    [-(400 + 137 * i % 2600) for i in range(40)], kind="direct_debit", start=100)
    found = _detect(fees + tickets)
    assert [(s.current_cents, len(s.txns)) for s in found] == [(-560, 12)]


def test_regular_coffee_is_not_a_subscription():
    dates = [date(2025, 3, 1) + timedelta(days=d) for d in (0, 3, 4, 11, 12, 20, 33, 34, 41, 55, 58, 70)]
    assert _detect(_txns("Koffiebar", dates, [-340] * 12, kind="card")) == []


def test_yearly_needs_the_merchant_to_be_otherwise_quiet():
    yearly = _txns("ANWB", [date(2025, 6, 15), date(2026, 6, 15)], [-6400, -6400])
    assert [s.cadence.name for s in _detect(yearly)] == ["yearly"]

    groceries = _txns("Lidl", [date(2025, 3, 1) + timedelta(days=3 * i) for i in range(150)],
                      [-(500 + 3719 * i % 5000) for i in range(150)], kind="card")
    groceries += _txns("Lidl", [date(2025, 5, 2), date(2026, 5, 2)], [-2186, -2186], kind="card", start=500)
    assert _detect(groceries) == []
