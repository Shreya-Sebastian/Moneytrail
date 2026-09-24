"""ABN AMRO tab-separated TXT export.

There is no header and no counterparty column: the name, IBAN and remittance text
are all packed into one fixed-width description, so they're pulled back out here.
"""

from __future__ import annotations

import re
from datetime import datetime

from ..model import Transaction
from .common import RowBuilder, parse_amount

_LABELS = "Incassant|Naam|Machtiging|Omschrijving|IBAN|BIC|Kenmerk"
FIELD = re.compile(rf"({_LABELS}):\s*(.*?)(?=\s+(?:{_LABELS}):|$)")
CARD = re.compile(r"^(BEA|GEA),\s*(?:Apple Pay|Google Pay|Betaalpas)?\s+(.*?),PAS\d+")


def sniff(text: str) -> bool:
    fields = text.split("\n", 1)[0].split("\t")
    return len(fields) == 8 and fields[1] == "EUR" and fields[2].isdigit() and len(fields[2]) == 8


def split_description(desc: str) -> tuple[str, str, str, str]:
    """-> (kind hint, counterparty, iban, remittance)."""
    card = CARD.match(desc)
    if card:
        return ("card" if card.group(1) == "BEA" else "atm"), card.group(2), "", desc
    fields = {k: v.strip() for k, v in FIELD.findall(desc)}
    if desc.startswith("SEPA Incasso"):
        hint = "direct_debit"
    elif desc.startswith("SEPA iDEAL"):
        hint = "ideal"
    elif desc.startswith("SEPA Overboeking"):
        hint = "transfer"
    else:
        hint = "other"
    return hint, fields.get("Naam", ""), fields.get("IBAN", ""), fields.get("Omschrijving", desc)


def parse(text: str, source_file: str) -> list[Transaction]:
    builder = RowBuilder("abnamro", source_file)
    for line in text.splitlines():
        if not line.strip():
            continue
        account, _currency, booked, _value_date, _start, _end, amount, desc = line.split("\t")
        cents = parse_amount(amount)
        hint, counterparty, iban, remittance = split_description(" ".join(desc.split()))
        if hint == "transfer":
            hint = "transfer_out" if cents < 0 else "transfer_in"
        builder.add(
            account=account,
            booked=datetime.strptime(booked, "%Y%m%d").date(),
            amount_cents=cents,
            kind=hint,
            counterparty=counterparty,
            counterparty_iban=iban,
            description=remittance,
        )
    return builder.rows
