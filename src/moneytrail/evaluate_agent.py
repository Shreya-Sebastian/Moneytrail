"""Score the merchant investigator against synthetic ground truth.

Cases are the merchants `needs_investigation` picks out: every merchant with a legal
entity among its statement names. Most of them (Coolblue B.V., Ziggo B.V.) are already
named correctly by the rules, so the score shows both sides: hard cases the agent fixes,
and easy cases it breaks by renaming them.

Three ways of naming each case are compared:
- rules:    the name merchant resolution gave it
- no_tools: the same model, shown the same history, without any tools
- agent:    the investigator
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from rapidfuzz import fuzz, utils

from .evaluate import _statement
from .importers import parse_file
from .investigate import Finding, guess_without_tools, home_city, investigate, needs_investigation
from .llm import Chat
from .merchants import resolve
from .world import World

MODES = ("rules", "no_tools", "agent")


@dataclass
class Case:
    merchant_id: str
    expected: str
    category: str
    hard: bool
    finding: Finding

    @property
    def correct(self) -> bool:
        return _same_name(self.finding.final_name, self.expected)

    @property
    def rules_correct(self) -> bool:
        return _same_name(self.finding.rules_name, self.expected)


@dataclass
class ModeReport:
    mode: str
    cases: list[Case] = field(default_factory=list)

    def _share(self, cases: list[Case]) -> float:
        return sum(c.correct for c in cases) / len(cases) if cases else 0.0

    @property
    def hard(self) -> list[Case]:
        return [c for c in self.cases if c.hard]

    @property
    def easy(self) -> list[Case]:
        return [c for c in self.cases if not c.hard]

    def summary(self) -> dict:
        f = [c.finding for c in self.cases]
        with_category = [c for c in self.cases if c.finding.category]
        return {
            "mode": self.mode,
            "cases": len(self.cases),
            "hard_correct": f"{sum(c.correct for c in self.hard)}/{len(self.hard)}",
            "easy_correct": f"{sum(c.correct for c in self.easy)}/{len(self.easy)}",
            "fixed": sum(c.correct and not c.rules_correct for c in self.cases),
            "broken": sum(c.rules_correct and not c.correct for c in self.cases),
            "outcomes": dict(Counter(x.outcome for x in f)),
            "category_correct": f"{sum(c.finding.category == c.category for c in with_category)}/{len(with_category)}",
            "bad_citations": sum(not x.citations_ok for x in f if x.outcome == "named"),
            "mean_steps": round(statistics.mean(x.steps for x in f), 2) if f else 0,
            "mean_seconds": round(statistics.mean(x.seconds for x in f), 1) if f else 0,
            "tokens": sum(x.prompt_tokens + x.output_tokens for x in f),
        }


def _same_name(found: str, expected: str) -> bool:
    """Same criterion as the main evaluation: recognisably the true name."""
    return fuzz.token_set_ratio(found, expected, processor=utils.default_process) >= 85


def evaluate_agent(data_dir: str | Path, world: World, chat: Chat | None, modes=MODES,
                   out_dir: str | Path | None = None, progress=None) -> dict[str, ModeReport]:
    data_dir = Path(data_dir)
    txns = parse_file(_statement(data_dir))
    with (data_dir / "labels.csv").open(encoding="utf-8") as fh:
        labels = {int(r["source_row"]): r for r in csv.DictReader(fh)}
    label = {t.txn_id: labels[t.source_row] for t in txns}
    res = resolve(txns)
    city = home_city(txns)

    reports = {mode: ModeReport(mode) for mode in modes}
    merchants = [m for m in res.merchants.values() if needs_investigation(m)]
    for i, m in enumerate(merchants, 1):
        truth = Counter(label[t]["merchant_id"] for t in m.txn_ids).most_common(1)[0][0]
        row = next(label[t] for t in m.txn_ids if label[t]["merchant_id"] == truth)
        for mode in modes:
            if mode == "rules":
                finding = Finding(m.id, m.name, None, None, None, outcome="abstained")
            elif mode == "no_tools":
                finding = guess_without_tools(m, txns, chat, city)
            else:
                finding = investigate(m, txns, world, chat, city)
            case = Case(m.id, row["merchant_name"], row["category"], row["hard"] == "1", finding)
            reports[mode].cases.append(case)
            if progress:
                progress(f"[{i}/{len(merchants)}] {mode:<8} {m.name!r} -> {finding.final_name!r} "
                         f"({finding.outcome}, expected {case.expected!r}, {'ok' if case.correct else 'WRONG'})")

    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        for mode, rep in reports.items():
            with (out / f"{mode}.jsonl").open("w", encoding="utf-8") as fh:
                for c in rep.cases:
                    fh.write(json.dumps({**asdict(c), "correct": c.correct}, ensure_ascii=False, default=str) + "\n")
        (out / "summary.json").write_text(
            json.dumps([r.summary() for r in reports.values()], indent=2), encoding="utf-8"
        )
    return reports
