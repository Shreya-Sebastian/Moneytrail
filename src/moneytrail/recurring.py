"""Recurring payment detection: subscriptions, bills, rent, salary.

Goes beyond "same amount every month": handles four-weekly billing, yearly
renewals, price changes, a subscription hidden among ad-hoc purchases at the same
merchant, and payments that have quietly stopped.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from .merchants import Resolution
from .model import Transaction


@dataclass(frozen=True)
class Cadence:
    name: str
    days: float
    tolerance: float


CADENCES = (
    Cadence("weekly", 7, 2),
    Cadence("four_weekly", 28, 2),
    Cadence("monthly", 30.44, 4),
    Cadence("quarterly", 91.31, 10),
    Cadence("yearly", 365.25, 15),
)
PRICE_TOLERANCE = 0.03  # amounts within 3% count as the same price
BAND_RATIO = 1.35  # amounts further apart than this are different things (iCloud vs Apple Music)


@dataclass
class PriceChange:
    on: date
    old_cents: int
    new_cents: int


@dataclass
class Series:
    merchant_id: str
    merchant_name: str
    kind: str
    cadence: Cadence
    txns: list[Transaction]
    status: str  # "active" | "stopped"
    next_expected: date | None
    price_changes: list[PriceChange] = field(default_factory=list)

    @property
    def current_cents(self) -> int:
        return self.txns[-1].amount_cents

    @property
    def monthly_cents(self) -> int:
        return round(self.current_cents * 30.44 / self.cadence.days)

    @property
    def txn_ids(self) -> list[str]:
        return [t.txn_id for t in self.txns]


def detect(txns: list[Transaction], resolution: Resolution, as_of: date | None = None) -> list[Series]:
    if not txns:
        return []
    as_of = as_of or max(t.booked for t in txns)
    groups: dict[tuple, list[Transaction]] = defaultdict(list)
    for t in txns:
        groups[(resolution.merchant_of[t.txn_id], t.kind, t.amount_cents < 0)].append(t)

    found: list[Series] = []
    for (merchant_id, kind, _), items in groups.items():
        name = resolution.merchants[merchant_id].name
        bands = _amount_bands(items)
        for band in bands:
            series = _fit(band, merchant_id, name, kind, as_of, allow_pair=len(bands) == 1)
            if series:
                found.append(series)
                continue
            # A subscription can hide among ad-hoc spending at the same merchant
            # (a monthly NS Flex fee next to one-off train tickets): try each exact amount.
            by_amount: dict[int, list[Transaction]] = defaultdict(list)
            for t in band:
                by_amount[t.amount_cents].append(t)
            for same in by_amount.values():
                series = _fit(same, merchant_id, name, kind, as_of, allow_pair=False)
                if series:
                    found.append(series)
    return sorted(found, key=lambda s: s.monthly_cents)


def _amount_bands(items: list[Transaction]) -> list[list[Transaction]]:
    ordered = sorted(items, key=lambda t: abs(t.amount_cents))
    bands, current = [], [ordered[0]]
    for prev, t in zip(ordered, ordered[1:]):
        if abs(t.amount_cents) > BAND_RATIO * max(abs(prev.amount_cents), 1):
            bands.append(current)
            current = []
        current.append(t)
    bands.append(current)
    return [sorted(b, key=lambda t: t.booked) for b in bands]


def _same_price(a: int, b: int) -> bool:
    return abs(a - b) <= max(PRICE_TOLERANCE * max(abs(a), abs(b)), 2)


def _fit(
    items: list[Transaction], merchant_id: str, name: str, kind: str, as_of: date, allow_pair: bool = True
) -> Series | None:
    """`allow_pair=False` when `items` were picked out of a bigger pile of payments to the
    same merchant: two equal amounts a year apart at a supermarket are a coincidence."""
    items = sorted(items, key=lambda t: t.booked)
    if len(items) < (2 if allow_pair else 3):
        return None
    gaps = [(b.booked - a.booked).days for a, b in zip(items, items[1:])]
    if len(items) == 2:
        # two payments can only mean "yearly", and only at the same price
        options = [c for c in CADENCES if c.name == "yearly"]
        if not _same_price(items[0].amount_cents, items[1].amount_cents):
            return None
    else:
        options = list(CADENCES)

    best, best_err = None, None
    for c in options:
        errors = [abs(g - c.days) for g in gaps]
        on_time = sum(e <= c.tolerance for e in errors) / len(errors)
        if on_time < 0.75:
            continue
        err = statistics.median(errors)
        if best_err is None or err < best_err:
            best, best_err = c, err
    if best is None:
        return None

    changes = _price_changes(items)
    if changes is None:
        return None

    last = items[-1].booked
    overdue = best.days + max(2 * best.tolerance, 0.5 * best.days)
    stopped = (as_of - last).days > overdue
    return Series(
        merchant_id=merchant_id,
        merchant_name=name,
        kind=kind,
        cadence=best,
        txns=items,
        status="stopped" if stopped else "active",
        next_expected=None if stopped else last + timedelta(days=round(best.days)),
        price_changes=changes,
    )


def _segments(items: list[Transaction], same) -> list[list[Transaction]]:
    segments: list[list[Transaction]] = [[items[0]]]
    for t in items[1:]:
        if same(t.amount_cents, segments[-1][-1].amount_cents):
            segments[-1].append(t)
        else:
            segments.append([t])
    return segments


def _price_changes(items: list[Transaction]) -> list[PriceChange] | None:
    """Price steps that stuck. None if the amounts are too erratic to be one series.

    Erratic-ness is judged loosely (within 3% is the same price), but changes are
    found on exact amounts: fixed charges repeat to the cent, and a €1150 -> €1185
    rent rise is only 3%. A one-off different amount in the middle (a correction, a
    prorated month) is ignored; a new amount that repeats, or is the latest charge,
    is a price change. Variable bills get no price changes at all.
    """
    limit = max(3, len(items) // 4)
    if len(_segments(items, _same_price)) > limit:
        return None
    exact = _segments(items, int.__eq__)
    if len(exact) > limit:
        return []

    level = exact[0][0].amount_cents
    changes = []
    for i, seg in enumerate(exact[1:], start=1):
        sticks = len(seg) >= 2 or i == len(exact) - 1
        if sticks and seg[0].amount_cents != level:
            changes.append(PriceChange(seg[0].booked, level, seg[0].amount_cents))
            level = seg[0].amount_cents
    return changes
