"""Write synthetic transactions in each bank's export format, plus ground-truth labels.

Layouts are modelled on the real ING, Rabobank, ABN AMRO and bunq exports. The
transaction codes and remittance layouts are approximations. If an import of a real
file fails, compare it against these writers first.
"""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from pathlib import Path

from types import ModuleType

from . import catalog as dev_catalog
from .generate import SynthTxn, make_iban

BICS = {"INGB": "INGBNL2A", "RABO": "RABONL2U", "ABNA": "ABNANL2A", "TRIO": "TRIONL2U", "BUNQ": "BUNQNL2A"}
START_BALANCE = 250_000  # cents


def _bic(iban: str) -> str:
    return BICS.get(iban[4:8], "") if iban else ""


def _nl(cents: int, signed: bool = False) -> str:
    s = f"{abs(cents) / 100:.2f}".replace(".", ",")
    return (("-" if cents < 0 else "+") + s) if signed else s


def _balances(txns: list[SynthTxn]) -> dict[int, int]:
    balance, after = START_BALANCE, {}
    for t in txns:  # already chronological
        balance += t.amount_cents
        after[id(t)] = balance
    return after


def _ref(t: SynthTxn, n: int = 6) -> str:
    rng = random.Random(f"{t.booked}{t.time}{t.amount_cents}{t.name}")
    return "".join(rng.choices("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789", k=n))


# --- ING ---------------------------------------------------------------------

ING_CODES = {
    "card": ("BA", "Betaalautomaat"),
    "direct_debit": ("IC", "Incasso"),
    "ideal": ("ID", "iDEAL"),
    "transfer_out": ("GT", "Online bankieren"),
    "transfer_in": ("OV", "Overschrijving"),
    "atm": ("GM", "Geldautomaat"),
}


def _ing_notes(t: SynthTxn) -> str:
    when = f"{t.booked:%d-%m-%Y}"
    if t.kind in ("card", "atm"):
        return f"Pasvolgnr: 008 {when} {t.time} Transactie: {_ref(t)} Term: {_ref(t, 8)} Apple Pay NLD"
    if t.kind == "direct_debit":
        return (
            f"Naam: {t.name} Omschrijving: {t.remittance} IBAN: {t.iban} Kenmerk: {_ref(t, 12)} "
            f"Machtiging ID: {t.mandate} Incassant ID: {t.creditor_id} Doorlopende incasso Valutadatum: {when}"
        )
    if t.kind == "ideal":
        return f"Naam: {t.name} Omschrijving: {t.remittance} IBAN: {t.iban} Kenmerk: {when} {t.time} {_ref(t, 16)} Valutadatum: {when}"
    return f"Naam: {t.name} Omschrijving: {t.remittance} IBAN: {t.iban} Valutadatum: {when}"


def write_ing(txns: list[SynthTxn], account: str, path: Path) -> list[SynthTxn]:
    after = _balances(txns)
    ordered = list(reversed(txns))  # ING exports newest first
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";", quoting=csv.QUOTE_ALL)
        w.writerow(["Datum", "Naam / Omschrijving", "Rekening", "Tegenrekening", "Code", "Af Bij",
                    "Bedrag (EUR)", "Mutatiesoort", "Mededelingen", "Saldo na mutatie", "Tag"])
        for t in ordered:
            code, label = ING_CODES[t.kind]
            w.writerow([f"{t.booked:%Y%m%d}", t.name, account, t.iban, code, "Af" if t.amount_cents < 0 else "Bij",
                        _nl(t.amount_cents), label, _ing_notes(t), _nl(after[id(t)]), ""])
    return ordered


# --- Rabobank ----------------------------------------------------------------

RABO_CODES = {"card": "bc", "direct_debit": "ei", "ideal": "id", "transfer_out": "tb", "transfer_in": "cb", "atm": "ga"}
RABO_HEADER = [
    "IBAN/BBAN", "Munt", "BIC", "Volgnr", "Datum", "Rentedatum", "Bedrag", "Saldo na trn",
    "Tegenrekening IBAN/BBAN", "Naam tegenpartij", "Naam uiteindelijke partij", "Naam initiërende partij",
    "BIC tegenpartij", "Code", "Batch ID", "Transactiereferentie", "Machtigingskenmerk", "Incassant ID",
    "Betalingskenmerk", "Omschrijving-1", "Omschrijving-2", "Omschrijving-3", "Reden retour",
    "Oorspr bedrag", "Oorspr munt", "Koers",
]


def write_rabobank(txns: list[SynthTxn], account: str, path: Path) -> list[SynthTxn]:
    after = _balances(txns)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(RABO_HEADER)
        for n, t in enumerate(txns, start=1):
            w.writerow([
                account, "EUR", "RABONL2U", f"{n:018d}", f"{t.booked:%Y-%m-%d}", f"{t.booked:%Y-%m-%d}",
                _nl(t.amount_cents, signed=True), _nl(after[id(t)], signed=True), t.iban, t.name, "", "",
                _bic(t.iban), RABO_CODES[t.kind], "", _ref(t, 12) if t.kind != "card" else "", t.mandate,
                t.creditor_id, "", t.remittance, "", "", "", "", "", "",
            ])
    return txns


# --- ABN AMRO ----------------------------------------------------------------


def _abn_description(t: SynthTxn) -> str:
    if t.kind in ("card", "atm"):
        prefix = "BEA, Apple Pay" if t.kind == "card" else "GEA, Betaalpas"
        return f"{prefix:<33}{t.name},PAS042         NR:{_ref(t)}, {t.booked:%d.%m.%y}/{t.time.replace(':', '.')}   {t.city.upper()}"
    if t.kind == "direct_debit":
        return (
            f"SEPA Incasso algemeen doorlopend Incassant: {t.creditor_id}  Naam: {t.name}  "
            f"Machtiging: {t.mandate}  Omschrijving: {t.remittance}  IBAN: {t.iban}  Kenmerk: {_ref(t, 12)}"
        )
    if t.kind == "ideal":
        return f"{'SEPA iDEAL':<33}IBAN: {t.iban}        BIC: {_bic(t.iban)}  Naam: {t.name}  Omschrijving: {t.remittance}  Kenmerk: {_ref(t, 16)}"
    return f"{'SEPA Overboeking':<33}IBAN: {t.iban}        BIC: {_bic(t.iban)}  Naam: {t.name}  Omschrijving: {t.remittance}"


def write_abnamro(txns: list[SynthTxn], account: str, path: Path) -> list[SynthTxn]:
    after = _balances(txns)
    legacy_account = account[-10:].lstrip("0")
    with path.open("w", newline="", encoding="utf-8") as f:
        for t in txns:
            end = after[id(t)]
            amount = ("-" if t.amount_cents < 0 else "") + _nl(t.amount_cents)
            fields = [legacy_account, "EUR", f"{t.booked:%Y%m%d}", f"{t.booked:%Y%m%d}",
                      _nl(end - t.amount_cents), _nl(end), amount, _abn_description(t)]
            f.write("\t".join(fields) + "\n")
    return txns


# --- bunq --------------------------------------------------------------------


def _bunq_description(t: SynthTxn) -> str:
    if t.kind == "card":
        return f"{t.name} {t.city}, NL"
    if t.kind == "atm":
        return f"Cash withdrawal {t.name}"
    if t.kind == "direct_debit":
        return f"{t.remittance} | SEPA direct debit, mandate {t.mandate}"
    if t.kind == "ideal":
        return f"{t.remittance} | iDEAL"
    return t.remittance


def write_bunq(txns: list[SynthTxn], account: str, path: Path) -> list[SynthTxn]:
    ordered = list(reversed(txns))
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";", quoting=csv.QUOTE_ALL)
        w.writerow(["Date", "Interest Date", "Amount", "Account", "Counterparty", "Name", "Description"])
        for t in ordered:
            w.writerow([f"{t.booked:%Y-%m-%d}", f"{t.booked:%Y-%m-%d}", f"{t.amount_cents / 100:.2f}",
                        account, t.iban, t.name, _bunq_description(t)])
    return ordered


WRITERS = {
    "ing": (write_ing, "INGB", "statement.csv"),
    "rabobank": (write_rabobank, "RABO", "statement.csv"),
    "abnamro": (write_abnamro, "ABNA", "statement.txt"),
    "bunq": (write_bunq, "BUNQ", "statement.csv"),
}


def export(txns: list[SynthTxn], bank: str, out_dir: Path, catalog: ModuleType = dev_catalog) -> Path:
    """Write statement + labels.csv + truth.json into out_dir. Returns the statement path.

    `catalog` must be the one the transactions were generated from.
    """
    writer, bank_code, filename = WRITERS[bank]
    out_dir.mkdir(parents=True, exist_ok=True)
    statement = out_dir / filename
    ordered = writer(txns, make_iban(f"own:{bank}", bank_code), statement)

    with (out_dir / "labels.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source_row", "merchant_id", "merchant_name", "category", "kind", "recurring_id", "hard"])
        for row, t in enumerate(ordered):
            m = catalog.MERCHANTS[t.merchant_id]
            w.writerow([row, m.id, m.name, m.category, t.kind, t.recurring_id, int(m.hard)])

    series: dict[str, list[SynthTxn]] = defaultdict(list)
    for t in txns:
        if t.recurring_id:
            series[t.recurring_id].append(t)
    cancelled = {p.id for p in catalog.recurring_plans(1, 12) if p.stop is not None}
    truth = {"as_of": max(t.booked for t in txns).isoformat(), "recurring": {}}
    for rid, items in series.items():
        changes = [b.booked.isoformat() for a, b in zip(items, items[1:]) if a.amount_cents != b.amount_cents]
        truth["recurring"][rid] = {
            "merchant_id": items[0].merchant_id,
            "count": len(items),
            "stopped": rid in cancelled,
            "price_changes": changes,
        }
    (out_dir / "truth.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")
    return statement
