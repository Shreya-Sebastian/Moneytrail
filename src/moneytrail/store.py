"""Local DuckDB store. Re-importing the same or an overlapping export is a no-op."""

from __future__ import annotations

from pathlib import Path

import duckdb

from .model import Transaction

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    txn_id            VARCHAR PRIMARY KEY,
    bank              VARCHAR NOT NULL,
    account           VARCHAR NOT NULL,
    booked            DATE    NOT NULL,
    amount_cents      BIGINT  NOT NULL,
    kind              VARCHAR NOT NULL,
    counterparty      VARCHAR NOT NULL,
    counterparty_iban VARCHAR NOT NULL,
    description       VARCHAR NOT NULL,
    source_file       VARCHAR NOT NULL,
    source_row        INTEGER NOT NULL
)
"""

COLUMNS = (
    "txn_id, bank, account, booked, amount_cents, kind, counterparty, "
    "counterparty_iban, description, source_file, source_row"
)


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        self.con = duckdb.connect(str(path))
        self.con.execute(SCHEMA)

    def count(self) -> int:
        return self.con.execute("SELECT count(*) FROM transactions").fetchone()[0]

    def add(self, txns: list[Transaction]) -> int:
        """Insert transactions, skipping ones already stored. Returns how many were new."""
        before = self.count()
        if txns:
            self.con.executemany(
                f"INSERT OR IGNORE INTO transactions ({COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        t.txn_id, t.bank, t.account, t.booked, t.amount_cents, t.kind,
                        t.counterparty, t.counterparty_iban, t.description, t.source_file, t.source_row,
                    )
                    for t in txns
                ],
            )
        return self.count() - before

    def transactions(self) -> list[Transaction]:
        rows = self.con.execute(f"SELECT {COLUMNS} FROM transactions ORDER BY booked, txn_id").fetchall()
        return [Transaction(*row) for row in rows]

    def close(self) -> None:
        self.con.close()
