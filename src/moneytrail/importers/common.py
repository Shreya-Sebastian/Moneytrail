"""Helpers shared by the bank-specific parsers."""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

from ..model import Transaction, transaction_id


def read_text(path: str | Path) -> str:
    raw = Path(path).read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # older exports from some banks are Latin-1
        return raw.decode("latin-1")


def parse_amount(text: str) -> int:
    """'1.234,56', '-12,34', '+12.34' or '12.34' -> cents.

    Dutch exports always carry two decimals, so whichever separator comes last is
    the decimal one.
    """
    s = text.strip().replace(" ", "")
    sign = -1 if s.startswith("-") else 1
    s = s.lstrip("+-")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    whole, _, frac = s.partition(".")
    frac = (frac + "00")[:2]
    return sign * (int(whole or 0) * 100 + int(frac))


def kind_from_code(code: str, cents: int, codes: dict[str, str], transfer_codes: set[str]) -> str:
    if code in codes:
        return codes[code]
    if code in transfer_codes:
        return "transfer_out" if cents < 0 else "transfer_in"
    return "other"


class RowBuilder:
    """Collects parsed rows into Transactions with stable ids."""

    def __init__(self, bank: str, source_file: str):
        self.bank = bank
        self.source_file = source_file
        self.rows: list[Transaction] = []
        self._seen: Counter[tuple] = Counter()

    def add(
        self,
        *,
        account: str,
        booked: date,
        amount_cents: int,
        kind: str,
        counterparty: str,
        counterparty_iban: str,
        description: str,
    ) -> None:
        counterparty = " ".join(counterparty.split())
        description = " ".join(description.split())
        account = account.strip()
        counterparty_iban = counterparty_iban.strip().replace(" ", "")
        key = (account, booked, amount_cents, counterparty, description)
        occurrence = self._seen[key]
        self._seen[key] += 1
        self.rows.append(
            Transaction(
                txn_id=transaction_id(
                    self.bank, account, booked, amount_cents, counterparty, description, occurrence
                ),
                bank=self.bank,
                account=account,
                booked=booked,
                amount_cents=amount_cents,
                kind=kind,
                counterparty=counterparty,
                counterparty_iban=counterparty_iban,
                description=description,
                source_file=self.source_file,
                source_row=len(self.rows),
            )
        )
