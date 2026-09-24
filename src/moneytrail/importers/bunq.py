"""bunq CSV export.

bunq has no transaction-type column, so the kind is inferred from the
description and whether there's a counterparty IBAN.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from ..model import Transaction
from .common import RowBuilder, parse_amount


def sniff(text: str) -> bool:
    first = text.split("\n", 1)[0]
    return '"Counterparty"' in first and '"Interest Date"' in first


def _kind(cents: int, iban: str, description: str) -> str:
    d = description.lower()
    if cents > 0:
        return "transfer_in"
    if "cash withdrawal" in d:
        return "atm"
    if "sepa direct debit" in d:
        return "direct_debit"
    if "ideal" in d:
        return "ideal"
    return "card" if not iban else "transfer_out"


def parse(text: str, source_file: str) -> list[Transaction]:
    first = text.split("\n", 1)[0]
    delimiter = ";" if first.count(";") > first.count(",") else ","
    builder = RowBuilder("bunq", source_file)
    for row in csv.DictReader(io.StringIO(text), delimiter=delimiter):
        cents = parse_amount(row["Amount"])
        iban = row["Counterparty"].strip()
        builder.add(
            account=row["Account"],
            booked=datetime.strptime(row["Date"].strip(), "%Y-%m-%d").date(),
            amount_cents=cents,
            kind=_kind(cents, iban, row["Description"]),
            counterparty=row["Name"],
            counterparty_iban=iban,
            description=row["Description"],
        )
    return builder.rows
