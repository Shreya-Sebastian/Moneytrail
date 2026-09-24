"""Merchant resolution: many messy statement names -> one merchant.

`AH 1234 UTRECHT`, `ALBERT HEIJN 5521` and `AH to go 0231 AMSTERDAM` are the same
shop; `SumUp  *Bakkerij Jansen` and `CCV*BAKKERIJ JANSEN` are the same bakery.

v1 is deliberately rule-based: normalise each name, then merge names that share a
counterparty IBAN or look alike (fuzzy match, truncation, acronym). It has no way of
knowing that `CCV*JV HOLDING B.V.` trades as a cafe; those cases are left for the
investigator agent and show up as naming misses in the evaluation.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from .model import Transaction

# Card terminals and payment providers prefix the shop name: "CCV*", "SumUp  *", "Zettle_*".
PROCESSOR = re.compile(
    r"^\s*(?:ccv|sumup|zettle|bck|pay\.nl|mollie|adyen|stripe|paypal|sq|takeaway\.com)\s*[*_]+\s*",
    re.I,
)
# "NS GROEP IZ NS REIZIGERS" / "AAB INZ TIKKIE": X on behalf of ("inzake") Y. Y is the merchant.
ON_BEHALF = re.compile(r"^.*?\b(?:iz|inz|inzake)\b\s+", re.I)
# "Thuisbezorgd.nl via Takeaway.com": the part before "via" is what people recognise.
VIA = re.compile(r"\s+via\s+.*$", re.I)
# Payment providers settle through a third-party-funds foundation ("derdengelden").
THIRD_PARTY_FUNDS = re.compile(r"^stichting\s+derdengelden\s+", re.I)
LEGAL_FORM = re.compile(r"\b(?:b\.?v\.?|n\.?v\.?|v\.?o\.?f\.?|gmbh|ltd|inc)(?=\s|$|[,.])", re.I)
TLD = re.compile(r"\.(?:com|nl|eu|de|be|io|co\.uk)\b", re.I)
DOMAIN_ONLY = re.compile(r"^\w+\.(?:com|nl|eu)$", re.I)

CITIES = (
    "den haag", "'s-gravenhage", "den bosch", "'s-hertogenbosch", "amsterdam", "rotterdam",
    "utrecht", "eindhoven", "groningen", "tilburg", "almere", "breda", "nijmegen", "apeldoorn",
    "haarlem", "arnhem", "enschede", "amersfoort", "zaandam", "leiden", "delft", "zwolle",
    "maastricht", "dordrecht", "zeist", "nieuwegein", "houten", "hilversum", "schiphol",
)
CITY = re.compile(r"\b(?:" + "|".join(re.escape(c) for c in CITIES) + r")\b", re.I)
# Words that say where or what kind of company it is, not which one.
FILLER = {"nederland", "netherlands", "international", "europe", "benelux", "nl", "klantenservice", "holland"}
# Words that are too generic to identify a merchant on their own ("restaurant", "de").
GENERIC = {
    "restaurant", "cafe", "eetcafe", "bar", "koffiebar", "bakkerij", "pizzeria", "hotel", "shop",
    "store", "winkel", "markt", "supermarkt", "de", "het", "van", "la", "le", "the", "en", "and",
}


def _strip_truncated_city(s: str) -> str:
    """'Albert Heijn 4321 Utre': the terminal cut the city off mid-word."""
    head, _, last = s.rstrip().rpartition(" ")
    if head and len(last) >= 3 and any(c.startswith(last.lower()) for c in CITIES if " " not in c):
        return head
    return s


def _strip_wrappers(name: str) -> str:
    s = THIRD_PARTY_FUNDS.sub("", name.strip())
    s = PROCESSOR.sub("", s)
    s = ON_BEHALF.sub("", s)
    s = VIA.sub("", s)
    s = LEGAL_FORM.sub(" ", s)
    return _strip_truncated_city(CITY.sub(" ", s))


def normalize(name: str) -> str:
    """Matching key for a statement name: lower case, no locations, numbers or legal forms."""
    s = TLD.sub("", _strip_wrappers(name))
    s = re.sub(r"[^\w\s]", " ", s.lower())
    tokens = [t for t in s.split() if not any(c.isdigit() for c in t) and t not in FILLER]
    if len(tokens) > 1 and tokens[-1] == "ab":  # Swedish "aktiebolag": "Spotify AB"
        tokens.pop()
    return " ".join(tokens) or name.strip().lower()


def display_name(name: str) -> str:
    """Readable version of a statement name, keeping its original casing."""
    s = _strip_wrappers(name)
    s = " ".join(t for t in s.split() if not any(c.isdigit() for c in t))
    s = s.strip(" ,.-*_")
    if not DOMAIN_ONLY.match(s):
        s = TLD.sub("", s)
    s = re.sub(r"[/_*]+", " ", s)
    words = [w for w in s.split() if w.lower() not in FILLER] or s.split()
    # "ALBERT HEIJN" -> "Albert Heijn", but a short all-caps word on its own is usually an
    # acronym (ANWB, HEMA, NS). In an all-caps multi-word name the terminal is just shouting.
    shouting = len(words) > 1 and all(w.isupper() for w in words if w.isalpha())
    words = [
        w.capitalize()
        if w.isupper() and (len(w) > 4 or w.lower() in GENERIC or (shouting and len(w) > 3))
        else w
        for w in words
    ]
    return " ".join(words) or name.strip()


def _acronym(short: list[str], long: list[str]) -> bool:
    """'ah' vs 'albert heijn'."""
    head = short[0]
    return (
        2 <= len(head) <= 4
        and len(long) == len(head)
        and not set(long) & GENERIC
        and head == "".join(w[0] for w in long)
    )


def similar(a: str, b: str) -> bool:
    if a == b:
        return True
    short, long = sorted((a, b), key=len)
    if len(short) >= 6 and long.startswith(short):  # card terminals truncate names
        return True
    s_tokens, l_tokens = short.split(), long.split()
    if set(s_tokens) <= set(l_tokens) and set(s_tokens) - GENERIC:
        return True
    if _acronym(s_tokens, l_tokens) or _acronym(l_tokens, s_tokens):
        return True
    return fuzz.token_sort_ratio(a, b) >= 90


@dataclass
class Merchant:
    id: str
    name: str
    txn_ids: list[str] = field(default_factory=list)
    raw_names: Counter[str] = field(default_factory=Counter)


@dataclass
class Resolution:
    merchants: dict[str, Merchant]
    merchant_of: dict[str, str]  # txn_id -> merchant id

    def merchant(self, txn_id: str) -> Merchant:
        return self.merchants[self.merchant_of[txn_id]]


def _raw_name(t: Transaction) -> str:
    return t.counterparty or t.description[:40] or "(unknown)"


def resolve(txns: list[Transaction]) -> Resolution:
    keys = sorted({normalize(_raw_name(t)) for t in txns})
    parent = {k: k for k in keys}

    def find(k: str) -> str:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    # A shared counterparty IBAN is the strongest signal there is.
    by_iban: dict[str, str] = {}
    for t in txns:
        if t.counterparty_iban:
            key = normalize(_raw_name(t))
            union(by_iban.setdefault(t.counterparty_iban, key), key)

    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            if find(a) != find(b) and similar(a, b):
                union(a, b)

    groups: dict[str, list[Transaction]] = defaultdict(list)
    for t in txns:
        groups[find(normalize(_raw_name(t)))].append(t)

    merchants: dict[str, Merchant] = {}
    merchant_of: dict[str, str] = {}
    for members in sorted(groups.values(), key=len, reverse=True):
        raw = Counter(_raw_name(t) for t in members)
        name = _renamed_to(members) or _pick_name(raw)
        mid = _unique_id(_slug(name), merchants)
        merchants[mid] = Merchant(mid, name, [t.txn_id for t in members], raw)
        for t in members:
            merchant_of[t.txn_id] = mid
    return Resolution(merchants, merchant_of)


RENAME_MIN = 3  # payments needed under both the old and the new name


def _renamed_to(members: list[Transaction]) -> str | None:
    """The new name, if the merchant switched names part-way through.

    'T-Mobile Netherlands B.V.' is used until one month, 'Odido Netherlands B.V.' from
    the next on. Name variants that interleave (AH / Albert Heijn) are not a rename.
    """
    spans: dict[str, list] = {}
    for t in members:
        key = display_name(_raw_name(t)).lower()
        first, last, n = spans.get(key, (t.booked, t.booked, 0))
        spans[key] = [min(first, t.booked), max(last, t.booked), n + 1]
    if len(spans) < 2:
        return None
    newest = max(spans, key=lambda k: spans[k][0])
    first_new, _, n_new = spans[newest]
    older = [s for k, s in spans.items() if k != newest]
    if n_new < RENAME_MIN or sum(s[2] for s in older) < RENAME_MIN:
        return None
    if any(last >= first_new for _, last, _ in older):
        return None
    latest = max((t for t in members if display_name(_raw_name(t)).lower() == newest), key=lambda t: t.booked)
    return display_name(_raw_name(latest))


def _pick_name(raw: Counter[str]) -> str:
    """Longest readable name among the variants that account for a fair share of use.

    Longest because statement names are abbreviated far more often than padded:
    'Albert Heijn' beats 'AH'.
    """
    total = sum(raw.values())
    candidates: Counter[str] = Counter()  # keyed case-insensitively: "LIDL" and "Lidl" are one name
    spellings: dict[str, Counter[str]] = defaultdict(Counter)
    for name, n in raw.items():
        shown = display_name(name)
        candidates[shown.lower()] += n
        spellings[shown.lower()][shown] += n
    common = [n for n, c in candidates.items() if c >= 0.15 * total] or list(candidates)
    best = max(common, key=lambda n: (len(n), candidates[n]))
    # prefer a spelling someone typed with normal casing over a terminal's ALL CAPS
    return max(spellings[best], key=lambda s: (not s.isupper(), spellings[best][s]))


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "merchant"


def _unique_id(base: str, taken: dict) -> str:
    mid, n = base, 2
    while mid in taken:
        mid, n = f"{base}-{n}", n + 1
    return mid
