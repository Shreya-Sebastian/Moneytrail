"""Generate a persona's transaction history with ground-truth labels."""

from __future__ import annotations

import calendar
import math
import random
from dataclasses import dataclass
from datetime import date, timedelta
from types import ModuleType

from . import catalog as dev_catalog
from .catalog import Plan, Spend

MONTHS_NL = (
    "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december",
)
IBAN_BANKS = ("INGB", "RABO", "ABNA", "TRIO", "BUNQ")


@dataclass
class SynthTxn:
    booked: date
    time: str
    amount_cents: int  # negative = money out
    kind: str
    name: str  # counterparty name as the bank would print it
    iban: str
    remittance: str
    city: str
    mandate: str
    creditor_id: str
    merchant_id: str
    recurring_id: str = ""


def make_iban(seed: str, bank: str | None = None) -> str:
    """A syntactically valid Dutch IBAN, deterministic per seed."""
    rng = random.Random(seed)
    bank = bank or rng.choice(IBAN_BANKS)
    bban = bank + f"{rng.randrange(10**9, 10**10)}"
    numeric = "".join(str(int(c, 36)) for c in bban + "NL00")
    return f"NL{98 - int(numeric) % 97:02d}{bban}"


def _month(first: date, offset: int) -> date:
    y, m = divmod(first.month - 1 + offset, 12)
    return date(first.year + y, m + 1, 1)


def _on_day(month: date, day: int) -> date:
    return month.replace(day=min(day, calendar.monthrange(month.year, month.month)[1]))


def _roll(d: date, direction: str) -> date:
    """Collections and transfers don't happen at weekends."""
    step = timedelta(days=1 if direction == "next" else -1)
    while d.weekday() >= 5:
        d += step
    return d


def _poisson(rng: random.Random, lam: float) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def _at(steps: tuple[tuple[int, object], ...], offset: int):
    return [v for start, v in steps if start <= offset][-1]


def _fill(cat: ModuleType, template: str, rng: random.Random, merchant: str, city: str, month: date) -> str:
    # each shop has a couple of branches the persona actually goes to
    branches = random.Random(f"{merchant}:{city}").sample(range(1000, 9999), 2)
    return template.format(
        store=rng.choice(branches),
        CITY=city.upper(),
        City=city,
        ref=rng.randrange(10**9, 10**10),
        what=rng.choice(cat.TIKKIE_WHAT),
        person=rng.choice(cat.PEOPLE),
        period=f"{month:%m-%Y}",
        month=f"{MONTHS_NL[month.month - 1]} {month.year}",
    )


def _time(rng: random.Random) -> str:
    return f"{rng.randint(8, 21):02d}:{rng.randint(0, 59):02d}"


def _mandate(merchant: str) -> tuple[str, str]:
    rng = random.Random(f"mandate:{merchant}")
    return f"{merchant[:6].upper()}{rng.randrange(10**7, 10**8)}", f"NL{rng.randint(10, 99)}ZZZ{rng.randrange(10**8, 10**9)}"


def _plan_dates(plan: Plan, first: date, months: int, end: date) -> list[tuple[int, date]]:
    stop = plan.stop if plan.stop is not None else months
    dates: list[tuple[int, date]] = []
    if plan.cadence == "monthly":
        dates = [(i, _on_day(_month(first, i), plan.day)) for i in range(plan.start, stop)]
    elif plan.cadence == "yearly":
        dates = [(i, _on_day(_month(first, i), plan.day)) for i in range(plan.start, stop, 12)]
    elif plan.cadence == "four_weekly":
        d, stop_date = _on_day(_month(first, plan.start), plan.day), _month(first, stop)
        while d < stop_date:
            offset = (d.year - first.year) * 12 + d.month - first.month
            dates.append((offset, d))
            d += timedelta(days=28)
    roll = {"card": "none", "transfer_in": "prev"}.get(plan.kind, "next")
    rolled = [(i, d if roll == "none" else _roll(d, roll)) for i, d in dates]
    return [(i, d) for i, d in rolled if d <= end]


def _recurring(cat: ModuleType, plan: Plan, first: date, months: int, end: date, rng: random.Random) -> list[SynthTxn]:
    sign = 1 if plan.kind == "transfer_in" else -1
    iban = "" if plan.kind == "card" else make_iban(f"iban:{plan.iban_owner or plan.merchant}")
    mandate, creditor = _mandate(plan.merchant) if plan.kind == "direct_debit" else ("", "")
    out = []
    for offset, d in _plan_dates(plan, first, months, end):
        out.append(
            SynthTxn(
                booked=d,
                time=_time(rng),
                amount_cents=sign * round(_at(plan.amounts, offset) * 100),
                kind=plan.kind,
                name=_at(plan.names, offset),
                iban=iban,
                remittance=_fill(cat, plan.remittance, rng, plan.merchant, cat.HOME_CITY, _month(first, offset)),
                city=cat.HOME_CITY,
                mandate=mandate,
                creditor_id=creditor,
                merchant_id=plan.merchant,
                recurring_id=plan.id,
            )
        )
    return out


def _adhoc(cat: ModuleType, spend: Spend, d: date, rng: random.Random) -> SynthTxn:
    city = cat.HOME_CITY if rng.random() < 0.85 else rng.choice(cat.OTHER_CITIES)
    weights = [1 / (i + 1) for i in range(len(spend.names))]
    template = rng.choices(spend.names, weights)[0]
    if spend.menu:
        euros = rng.choice(spend.amount)
    else:
        lo, hi = spend.amount
        euros = math.exp(rng.uniform(math.log(lo), math.log(hi)))  # small purchases are commoner
    sign = 1 if spend.kind == "transfer_in" else -1
    uses_iban = spend.kind in ("ideal", "transfer_in", "transfer_out")
    name = _fill(cat, template, rng, spend.merchant, city, d)
    # Some card terminals cut the name off at a fixed width; which ones, and at what
    # width, is a property of the terminal.
    terminal = random.Random(f"truncates:{spend.merchant}:{template}")
    if spend.kind == "card" and terminal.random() < cat.TRUNCATE_SHARE:
        name = name[: terminal.choice(cat.TERMINAL_WIDTHS)].rstrip()
    return SynthTxn(
        booked=d,
        time=_time(rng),
        amount_cents=sign * round(euros * 100),
        kind=spend.kind,
        name=name,
        iban=make_iban(f"iban:{spend.iban_owner or spend.merchant}") if uses_iban else "",
        remittance=_fill(cat, spend.remittance, rng, spend.merchant, city, d),
        city=city,
        mandate="",
        creditor_id="",
        merchant_id=spend.merchant,
    )


def generate(
    months: int = 18, end: date = date(2026, 8, 31), seed: int = 7, catalog: ModuleType = dev_catalog
) -> list[SynthTxn]:
    rng = random.Random(seed)
    first = _month(date(end.year, end.month, 1), -(months - 1))
    out: list[SynthTxn] = []
    for plan in catalog.recurring_plans(first.month, months):
        out += _recurring(catalog, plan, first, months, end, rng)
    for i in range(months):
        month = _month(first, i)
        ndays = calendar.monthrange(month.year, month.month)[1]
        for spend in catalog.ADHOC:
            for _ in range(_poisson(rng, spend.per_month)):
                d = month.replace(day=rng.randint(1, ndays))
                if d <= end:
                    out.append(_adhoc(catalog, spend, d, rng))
    out.sort(key=lambda t: (t.booked, t.time))
    return out
