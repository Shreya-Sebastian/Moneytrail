"""moneytrail command line."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .evaluate import evaluate
from .importers import parse_file
from .merchants import resolve
from .recurring import detect
from .store import Store
from .synth import CATALOGS, WRITERS, export, generate, load_catalog

DEFAULT_DB = "moneytrail.duckdb"


def _euro(cents: int) -> str:
    return f"{'-' if cents < 0 else ''}€{abs(cents) / 100:,.2f}"


def cmd_synth(args: argparse.Namespace) -> None:
    catalog = load_catalog(args.set)
    txns = generate(months=args.months, end=date.fromisoformat(args.end), seed=args.seed, catalog=catalog)
    banks = list(WRITERS) if args.bank == "all" else [args.bank]
    for bank in banks:
        path = export(txns, bank, Path(args.out) / bank, catalog=catalog)
        print(f"{bank:<9} {len(txns)} transactions -> {path}")


def cmd_import(args: argparse.Namespace) -> None:
    store = Store(args.db)
    for path in args.files:
        txns = parse_file(path, bank=args.bank)
        new = store.add(txns)
        bank = txns[0].bank if txns else "?"
        print(f"{path}: {len(txns)} rows ({bank}), {new} new, {len(txns) - new} already stored")
    print(f"{store.count()} transactions in {args.db}")


def cmd_merchants(args: argparse.Namespace) -> None:
    txns = Store(args.db).transactions()
    res = resolve(txns)
    amount = {t.txn_id: t.amount_cents for t in txns}
    rows = sorted(res.merchants.values(), key=lambda m: sum(amount[i] for i in m.txn_ids))
    print(f"{len(res.merchants)} merchants from {len(txns)} transactions\n")
    print(f"{'merchant':<28} {'txns':>5} {'total':>12}  statement names")
    for m in rows[: args.limit]:
        names = ", ".join(n for n, _ in m.raw_names.most_common(3))
        extra = f" (+{len(m.raw_names) - 3})" if len(m.raw_names) > 3 else ""
        print(f"{m.name[:28]:<28} {len(m.txn_ids):>5} {_euro(sum(amount[i] for i in m.txn_ids)):>12}  {names}{extra}")


def cmd_recurring(args: argparse.Namespace) -> None:
    txns = Store(args.db).transactions()
    series = detect(txns, resolve(txns))
    active = [s for s in series if s.status == "active"]
    print(f"{'merchant':<24} {'cadence':<12} {'amount':>10} {'per month':>10}  {'next':<10}  notes")
    for s in series:
        sign = "+" if s.current_cents > 0 else " "
        notes = []
        if s.status == "stopped":
            notes.append(f"stopped? last paid {s.txns[-1].booked}")
        for c in s.price_changes:
            notes.append(f"{_euro(abs(c.old_cents))} -> {_euro(abs(c.new_cents))} on {c.on}")
        nxt = s.next_expected.isoformat() if s.next_expected else "-"
        print(f"{s.merchant_name[:24]:<24} {s.cadence.name:<12} {sign + _euro(abs(s.current_cents)):>10} "
              f"{sign + _euro(abs(s.monthly_cents)):>10}  {nxt:<10}  {'; '.join(notes)}")
    out = sum(s.monthly_cents for s in active if s.current_cents < 0)
    print(f"\n{len(active)} active, recurring outgoings ≈ {_euro(-out)} per month")


def cmd_eval(args: argparse.Namespace) -> None:
    for d in args.dirs:
        r = evaluate(d)
        print(f"== {d}  ({r.transactions} transactions)")
        print(f"merchants   found {r.merchants_found} / true {r.merchants_true}")
        print(f"            B-cubed P {r.bcubed_precision:.3f}  R {r.bcubed_recall:.3f}  F1 {r.bcubed_f1:.3f}")
        print(f"            named correctly {r.name_accuracy:.1%} of txns  (legal-entity-only merchants: {r.name_accuracy_hard:.1%})")
        print(f"recurring   found {r.recurring_found} / true {r.recurring_true}  "
              f"P {r.recurring_precision:.3f}  R {r.recurring_recall:.3f}")
        print(f"            price changes caught {r.price_change_recall:.1%}  cancellations caught {r.stopped_recall:.1%}")
        if args.verbose:
            for found, expected, n in r.misnamed:
                print(f"  misnamed  {found!r} should be {expected!r} ({n} txns)")
            for rid in r.missed_series:
                print(f"  missed    {rid}")
            for s in r.spurious_series:
                print(f"  spurious  {s}")
        print()


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="moneytrail", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("synth", help="generate synthetic bank exports with ground truth")
    s.add_argument("--bank", choices=[*WRITERS, "all"], default="all")
    s.add_argument("--set", choices=list(CATALOGS), default="dev", help="which merchant catalogue to use")
    s.add_argument("--months", type=int, default=18)
    s.add_argument("--end", default="2026-08-31")
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--out", default="data/demo")
    s.set_defaults(func=cmd_synth)

    s = sub.add_parser("import", help="import bank export files")
    s.add_argument("files", nargs="+")
    s.add_argument("--bank", choices=list(WRITERS), help="skip auto-detection")
    s.add_argument("--db", default=DEFAULT_DB)
    s.set_defaults(func=cmd_import)

    s = sub.add_parser("merchants", help="list resolved merchants")
    s.add_argument("--db", default=DEFAULT_DB)
    s.add_argument("--limit", type=int, default=30)
    s.set_defaults(func=cmd_merchants)

    s = sub.add_parser("recurring", help="list subscriptions and other recurring payments")
    s.add_argument("--db", default=DEFAULT_DB)
    s.set_defaults(func=cmd_recurring)

    s = sub.add_parser("eval", help="score against synthetic ground truth")
    s.add_argument("dirs", nargs="+")
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(func=cmd_eval)

    args = p.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args.func(args)


if __name__ == "__main__":
    main()
