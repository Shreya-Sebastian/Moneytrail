"""Synthetic bank exports with ground truth, so every component can be measured.

Two catalogues:
- "dev": written alongside the resolution rules. Fine for development, flattering as a score.
- "heldout": written separately, from a description of statement messiness only, without
  seeing the rules. Used for reporting, never for tuning.
"""

from importlib import import_module
from types import ModuleType

from .export import WRITERS, export
from .generate import SynthTxn, generate

CATALOGS = {"dev": "moneytrail.synth.catalog", "heldout": "moneytrail.synth.heldout"}


def load_catalog(name: str) -> ModuleType:
    return import_module(CATALOGS[name])


__all__ = ["CATALOGS", "WRITERS", "SynthTxn", "export", "generate", "load_catalog"]
