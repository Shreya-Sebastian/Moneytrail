"""ING CSV export ("Af- en bijschrijvingen"), semicolon or comma separated."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from ..model import Transaction
from .common import RowBuilder, kind_from_code, parse_amount

CODES = {"BA": "card", "IC": "direct_debit", "ID": "ideal", "GM": "atm"}
TRANSFER_CODES = {"GT", "OV", "ST", "DV"}


def sniff(text: str) -> bool:
    first = text.split("\n", 1)[0]
    return "Naam / Omschrijving" in first and "Af Bij" in first


def parse(text: str, source_file: str) -> list[Transaction]:
    first = text.split("\n", 1)[0]
    delimiter = ";" if first.count(";") > first.count(",") else ","
    builder = RowBuilder("ing", source_file)
    for row in csv.DictReader(io.StringIO(text), delimiter=delimiter):
        cents = parse_amount(row["Bedrag (EUR)"])
        if row["Af Bij"].strip().lower() == "af":
            cents = -cents
        builder.add(
            account=row["Rekening"],
            booked=datetime.strptime(row["Datum"].strip(), "%Y%m%d").date(),
            amount_cents=cents,
            kind=kind_from_code(row["Code"].strip().upper(), cents, CODES, TRANSFER_CODES),
            counterparty=row["Naam / Omschrijving"],
            counterparty_iban=row["Tegenrekening"],
            description=row["Mededelingen"],
        )
    return builder.rows
