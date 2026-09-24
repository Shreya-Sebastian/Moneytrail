"""Rabobank CSV export (comma separated, every field quoted)."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from ..model import Transaction
from .common import RowBuilder, kind_from_code, parse_amount

CODES = {"bc": "card", "ei": "direct_debit", "id": "ideal", "ga": "atm"}
TRANSFER_CODES = {"tb", "cb", "ov", "sb"}


def sniff(text: str) -> bool:
    first = text.split("\n", 1)[0]
    return "IBAN/BBAN" in first and "Naam tegenpartij" in first


def parse(text: str, source_file: str) -> list[Transaction]:
    builder = RowBuilder("rabobank", source_file)
    for row in csv.DictReader(io.StringIO(text)):
        cents = parse_amount(row["Bedrag"])
        description = " ".join(row.get(f"Omschrijving-{i}", "") for i in (1, 2, 3))
        builder.add(
            account=row["IBAN/BBAN"],
            booked=datetime.strptime(row["Datum"].strip(), "%Y-%m-%d").date(),
            amount_cents=cents,
            kind=kind_from_code(row["Code"].strip().lower(), cents, CODES, TRANSFER_CODES),
            counterparty=row["Naam tegenpartij"],
            counterparty_iban=row["Tegenrekening IBAN/BBAN"],
            description=description,
        )
    return builder.rows
