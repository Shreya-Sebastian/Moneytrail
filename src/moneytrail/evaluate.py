"""Score merchant resolution and recurring detection against synthetic ground truth."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from rapidfuzz import fuzz, utils

from .importers import parse_file
from .merchants import Resolution, resolve
from .model import Transaction
from .recurring import Series, detect


@dataclass
class Report:
    transactions: int
    merchants_true: int
    merchants_found: int
    bcubed_precision: float
    bcubed_recall: float
    name_accuracy: float  # share of transactions whose merchant got a recognisable name
    name_accuracy_hard: float  # same, for merchants that only show a legal entity name
    recurring_true: int
    recurring_found: int
    recurring_precision: float
    recurring_recall: float
    price_change_recall: float
    stopped_recall: float
    misnamed: list[tuple[str, str, int]] = field(default_factory=list)  # (found, expected, txns)
    missed_series: list[str] = field(default_factory=list)
    spurious_series: list[str] = field(default_factory=list)

    @property
    def bcubed_f1(self) -> float:
        p, r = self.bcubed_precision, self.bcubed_recall
        return 2 * p * r / (p + r) if p + r else 0.0


def _statement(data_dir: Path) -> Path:
    for name in ("statement.csv", "statement.txt"):
        if (data_dir / name).exists():
            return data_dir / name
    raise FileNotFoundError(f"no statement in {data_dir}")


def evaluate(data_dir: str | Path) -> Report:
    data_dir = Path(data_dir)
    txns = parse_file(_statement(data_dir))
    with (data_dir / "labels.csv").open(encoding="utf-8") as f:
        labels = {int(r["source_row"]): r for r in csv.DictReader(f)}
    truth = json.loads((data_dir / "truth.json").read_text(encoding="utf-8"))
    label = {t.txn_id: labels[t.source_row] for t in txns}

    resolution = resolve(txns)
    series = detect(txns, resolution)
    report = _score_merchants(txns, resolution, label)
    _score_recurring(report, txns, series, label, truth)
    return report


def _score_merchants(txns: list[Transaction], res: Resolution, label: dict) -> Report:
    pred = {t.txn_id: res.merchant_of[t.txn_id] for t in txns}
    true = {t.txn_id: label[t.txn_id]["merchant_id"] for t in txns}
    pred_size, true_size = Counter(pred.values()), Counter(true.values())
    overlap = Counter((pred[i], true[i]) for i in pred)
    n = len(txns)
    precision = sum(overlap[(pred[i], true[i])] / pred_size[pred[i]] for i in pred) / n
    recall = sum(overlap[(pred[i], true[i])] / true_size[true[i]] for i in pred) / n

    # A merchant is named well if its name is recognisably the true one ("NS Reizigers" for "NS").
    majority: dict[str, str] = {}
    by_pred: dict[str, Counter] = defaultdict(Counter)
    for i in pred:
        by_pred[pred[i]][true[i]] += 1
    for mid, counts in by_pred.items():
        majority[mid] = counts.most_common(1)[0][0]
    true_name = {label[i]["merchant_id"]: label[i]["merchant_name"] for i in label}
    hard = {label[i]["merchant_id"] for i in label if label[i]["hard"] == "1"}

    ok = ok_hard = n_hard = 0
    misnamed: Counter[tuple[str, str]] = Counter()
    for i in pred:
        found = res.merchants[pred[i]].name
        expected = true_name[true[i]]
        good = true[i] == majority[pred[i]] and fuzz.token_set_ratio(found, expected, processor=utils.default_process) >= 85
        ok += good
        if true[i] in hard:
            n_hard += 1
            ok_hard += good
        if not good:
            misnamed[(found, expected)] += 1

    return Report(
        transactions=n,
        merchants_true=len(true_size),
        merchants_found=len(pred_size),
        bcubed_precision=precision,
        bcubed_recall=recall,
        name_accuracy=ok / n,
        name_accuracy_hard=ok_hard / n_hard if n_hard else 1.0,
        recurring_true=0,
        recurring_found=0,
        recurring_precision=0.0,
        recurring_recall=0.0,
        price_change_recall=0.0,
        stopped_recall=0.0,
        misnamed=[(f, e, c) for (f, e), c in misnamed.most_common()],
    )


def _score_recurring(report: Report, txns: list[Transaction], series: list[Series], label: dict, truth: dict) -> None:
    true_series = truth["recurring"]
    true_count = Counter(label[t.txn_id]["recurring_id"] for t in txns if label[t.txn_id]["recurring_id"])
    matched: dict[str, Series] = {}
    spurious = []
    for s in series:
        rids = Counter(label[i]["recurring_id"] for i in s.txn_ids)
        rid, hits = rids.most_common(1)[0]
        if rid and hits >= 0.8 * len(s.txns) and hits >= 0.8 * true_count[rid] and rid not in matched:
            matched[rid] = s
        else:
            spurious.append(f"{s.merchant_name} ({s.cadence.name}, {len(s.txns)}x {s.current_cents / 100:.2f})")

    changes_true = changes_hit = 0
    for rid, info in true_series.items():
        expected = set(info["price_changes"])
        changes_true += len(expected)
        if rid in matched:
            found = {c.on.isoformat() for c in matched[rid].price_changes}
            changes_hit += len(expected & found)
    stopped = [rid for rid, info in true_series.items() if info["stopped"]]
    stopped_hit = sum(1 for rid in stopped if rid in matched and matched[rid].status == "stopped")

    report.recurring_true = len(true_series)
    report.recurring_found = len(series)
    report.recurring_precision = len(matched) / len(series) if series else 0.0
    report.recurring_recall = len(matched) / len(true_series) if true_series else 0.0
    report.price_change_recall = changes_hit / changes_true if changes_true else 1.0
    report.stopped_recall = stopped_hit / len(stopped) if stopped else 1.0
    report.missed_series = sorted(set(true_series) - set(matched))
    report.spurious_series = spurious
