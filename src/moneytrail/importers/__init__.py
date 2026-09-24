"""Turn bank exports into Transactions. The bank is detected from the file itself."""

from __future__ import annotations

from pathlib import Path

from ..model import Transaction
from . import abnamro, bunq, ing, rabobank
from .common import read_text

PARSERS = {"ing": ing, "rabobank": rabobank, "abnamro": abnamro, "bunq": bunq}


def detect_bank(text: str) -> str:
    for name, parser in PARSERS.items():
        if parser.sniff(text):
            return name
    raise ValueError("unrecognised export format (expected ING, Rabobank, ABN AMRO or bunq)")


def parse_file(path: str | Path, bank: str | None = None) -> list[Transaction]:
    text = read_text(path)
    bank = bank or detect_bank(text)
    return PARSERS[bank].parse(text, source_file=Path(path).name)
