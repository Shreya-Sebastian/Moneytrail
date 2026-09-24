"""The one shape every bank export gets turned into."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

KINDS = ("card", "direct_debit", "ideal", "transfer_out", "transfer_in", "atm", "other")


@dataclass(frozen=True)
class Transaction:
    txn_id: str
    bank: str
    account: str
    booked: date
    amount_cents: int  # negative = money out
    kind: str  # one of KINDS
    counterparty: str  # name as the bank shows it; may be empty
    counterparty_iban: str
    description: str
    source_file: str
    source_row: int  # 0-based data row in the export, for tracing a result back to the file

    @property
    def amount(self) -> float:
        return self.amount_cents / 100


def transaction_id(
    bank: str,
    account: str,
    booked: date,
    amount_cents: int,
    counterparty: str,
    description: str,
    occurrence: int,
) -> str:
    """Stable id, so importing overlapping exports doesn't double-count.

    `occurrence` numbers exact duplicates within one file (two identical coffees on
    the same day), which keeps them distinct while still matching across files.
    """
    key = "|".join(
        [bank, account, booked.isoformat(), str(amount_cents), counterparty, description, str(occurrence)]
    )
    return hashlib.sha1(key.encode()).hexdigest()[:16]
