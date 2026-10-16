"""A small simulated outside world for the merchant investigator to search.

The synthetic personas pay shops that don't exist, so a real company register or map
can't say who `CCV*JV HOLDING B.V.` is. Instead each catalogue gets a world: a
register in the style of the Dutch business register (legal name, trade names,
address, activity) and a map of places (name, kind, address).

Most entries are derived from the catalogue itself: a shop that trades under its own
name gets a register entry and, if it has premises, a place. Shops that only show a
legal name, plus look-alike companies that should not be confused with them, are
written by hand in `synth/world_<set>.py`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import import_module
from types import ModuleType

from rapidfuzz import fuzz, utils

from .merchants import LEGAL_FORM
from .synth import load_catalog


@dataclass(frozen=True)
class Company:
    kvk: str  # registration number
    legal_name: str
    trade_names: tuple[str, ...]
    street: str
    city: str
    activity: str


@dataclass(frozen=True)
class Place:
    name: str
    kind: str  # "cafe", "restaurant", "supermarket", ...
    street: str
    city: str


# What kind of premises a merchant of each category has, for the derived places.
PLACE_KIND = {
    "groceries": "shop",
    "eating_out": "restaurant",
    "shopping": "shop",
    "personal_care": "shop",
    "health_fitness": "sports centre",
    "entertainment": "venue",
}
ACTIVITY = {
    "groceries": "Retail sale of food",
    "eating_out": "Restaurants and cafes",
    "shopping": "Retail trade",
    "personal_care": "Retail sale of personal care products",
    "health_fitness": "Sports facilities",
    "entertainment": "Entertainment and media",
    "utilities": "Utilities and telecommunications",
    "insurance": "Insurance",
    "housing": "Letting of residential property",
    "transport": "Passenger transport",
    "education": "Education services",
    "income": "Business activities",
}
NO_ENTRY = {"transfers", "savings", "cash"}  # people and own accounts aren't in a company register


@dataclass
class World:
    companies: list[Company] = field(default_factory=list)
    places: list[Place] = field(default_factory=list)

    def search_register(self, query: str, city: str | None = None, limit: int = 5) -> list[Company]:
        """Companies whose legal or trade name looks like `query`, best first."""
        q = _key(query)
        scored = []
        for c in self.companies:
            if city and c.city.lower() != city.lower():
                continue
            score = max(fuzz.token_set_ratio(q, _key(n)) for n in (c.legal_name, *c.trade_names))
            if score >= 70:
                scored.append((score, c))
        scored.sort(key=lambda sc: -sc[0])
        return [c for _, c in scored[:limit]]

    def register_entry(self, kvk: str) -> Company | None:
        return next((c for c in self.companies if c.kvk == kvk), None)

    def search_map(
        self, name: str | None = None, street: str | None = None, city: str | None = None, limit: int = 5
    ) -> list[Place]:
        out = []
        for p in self.places:
            if city and p.city.lower() != city.lower():
                continue
            if street and fuzz.token_set_ratio(street, p.street, processor=utils.default_process) < 90:
                continue
            if name:
                score = fuzz.token_set_ratio(_key(name), _key(p.name))
                if score < 70:
                    continue
            out.append(p)
        return out[:limit]


def _key(name: str) -> str:
    """Names compared without legal forms or punctuation: 'JV Holding B.V.' ~ 'jv holding'."""
    s = LEGAL_FORM.sub(" ", name)
    return re.sub(r"[^\w\s]", " ", s.lower()).strip()


def _legal_name(names: list[str], fallback: str) -> str:
    """A statement name that is a legal entity, without a branch number or city in it."""
    for n in names:
        if "{" not in n and LEGAL_FORM.search(n):
            return n
    return f"{fallback} B.V."


def _statement_names(catalog: ModuleType) -> dict[str, list[str]]:
    names: dict[str, list[str]] = {}
    for s in catalog.ADHOC:
        names.setdefault(s.merchant, []).extend(s.names)
    first, months = 1, 18
    for p in catalog.recurring_plans(first, months):
        names.setdefault(p.merchant, []).extend(n for _, n in p.names)
    return names


def build_world(set_name: str) -> World:
    catalog = load_catalog(set_name)
    extra = import_module(f"moneytrail.synth.world_{set_name}")
    names = _statement_names(catalog)
    world = World(companies=list(extra.COMPANIES), places=list(extra.PLACES))
    for i, m in enumerate(catalog.MERCHANTS.values()):
        if m.hard or m.category in NO_ENTRY:
            continue
        legal = _legal_name(names.get(m.id, []), m.name)
        street = f"{('Hoofdstraat', 'Stationsplein', 'Marktstraat', 'Industrieweg')[i % 4]} {10 + i}"
        world.companies.append(
            Company(f"{70000000 + i * 7919:08d}", legal, (m.name,), street, catalog.HOME_CITY, ACTIVITY[m.category])
        )
        if m.category in PLACE_KIND:
            world.places.append(Place(m.name, PLACE_KIND[m.category], street, catalog.HOME_CITY))
    return world


def company_dict(c: Company) -> dict:
    return {
        "kvk": c.kvk, "legal_name": c.legal_name, "trade_names": list(c.trade_names),
        "address": f"{c.street}, {c.city}", "activity": c.activity,
    }


def place_dict(p: Place) -> dict:
    return {"name": p.name, "kind": p.kind, "address": f"{p.street}, {p.city}"}
