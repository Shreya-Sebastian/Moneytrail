"""Merchant investigator: a tool-using agent for merchants the rules can't name.

`CCV*JV HOLDING B.V.` is a cafe, but nothing in the statement says so. The agent gets
the merchant's payment history and can search the rest of the account's history, a
company register and a map. It answers with a name and category, the confidence it
has in them, and the tool results it relied on.

Two safeguards, because a wrong name is worse than a legal name:
- the agent may answer "unknown", and is told that is better than a guess;
- an answer is only accepted if the name appears in something a tool returned (or in
  the statements). A name the model made up is rejected and the rules' name is kept.
"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from dataclasses import dataclass, field

from rapidfuzz import fuzz, utils

from .llm import Chat, Reply
from .merchants import CITY, LEGAL_FORM, Merchant, Resolution
from .model import Transaction
from .world import World, company_dict, place_dict

CATEGORIES = (
    "groceries", "eating_out", "shopping", "personal_care", "health_fitness", "transport",
    "entertainment", "utilities", "insurance", "housing", "education", "income",
    "transfers", "savings", "cash",
)
# Words that say a statement name is a company behind a shop rather than the shop.
ENTITY_WORDS = re.compile(r"\b(?:holding|horeca|catering|beheer|exploitatie|stichting|stg)\b", re.I)
MAX_STEPS = 8

SYSTEM_PROMPT = """\
You identify merchants on Dutch bank statements. A statement sometimes shows only the \
company behind a shop (a holding, a V.O.F., a B.V.) instead of the name a customer knows. \
Find the name a customer would recognise, usually the shop's trade name, and its category.

How to work:
- Look at the merchant's history first: payment type, amounts, cities in the names.
- Search the company register for the legal name. Read the entry: its trade names, \
address and activity.
- A register search can return companies with similar names in other cities. Prefer \
the one in the account holder's home city unless the statements point elsewhere.
- A company can have several trade names. Check the map for what is at each address, and \
pick the one that fits how this person pays (small card payments mean premises they \
visit, such as a cafe or shop; direct debits mean a service).
- If the statement name already is the name a customer knows, such as a brand, keep it.

Rules:
- Only answer with a name that appears in a tool result or the statement names.
- If the evidence does not settle it, answer with name null. A wrong name is worse than \
no name.
- Finish by calling final_answer, citing the step numbers of the tool results you used.\
"""

TOOLS = [
    {"type": "function", "function": {
        "name": "merchant_history",
        "description": "Payments to or from the merchant being investigated: statement names, payment "
                       "types, amounts, dates, cities in the names and sample descriptions.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "search_history",
        "description": "Search all of the account's transactions (names and descriptions) for a text.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    }},
    {"type": "function", "function": {
        "name": "search_register",
        "description": "Search the company register by legal name or trade name. Returns registration "
                       "number (kvk), legal name, trade names, address and activity.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"},
            "city": {"type": "string", "description": "optional, only companies registered in this city"},
        }, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "get_register_entry",
        "description": "Full register entry for a registration number (kvk).",
        "parameters": {"type": "object", "properties": {"kvk": {"type": "string"}}, "required": ["kvk"]},
    }},
    {"type": "function", "function": {
        "name": "search_map",
        "description": "Find places (shops, cafes, offices) by name and/or street and/or city.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}, "street": {"type": "string"}, "city": {"type": "string"},
        }},
    }},
    {"type": "function", "function": {
        "name": "final_answer",
        "description": "Give the answer and stop. Use name null when the evidence does not settle it.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": ["string", "null"], "description": "the name a customer would recognise"},
            "category": {"type": "string", "enum": list(CATEGORIES)},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "evidence": {"type": "array", "items": {"type": "object", "properties": {
                "step": {"type": "integer"}, "fact": {"type": "string"},
            }, "required": ["step", "fact"]}},
        }, "required": ["name", "category", "confidence", "evidence"]},
    }},
]


def needs_investigation(m: Merchant) -> bool:
    """The rules' name may be a company behind a shop: some statement name is a legal entity."""
    return any(LEGAL_FORM.search(n) or ENTITY_WORDS.search(n) for n in m.raw_names)


def home_city(txns: list[Transaction]) -> str:
    """The city that appears most in card payment names."""
    cities = Counter(
        c.group(0).title() for t in txns if t.kind == "card" for c in [CITY.search(t.counterparty or t.description)] if c
    )
    return cities.most_common(1)[0][0] if cities else ""


def _euros(cents: int) -> float:
    return round(cents / 100, 2)


def history_summary(m: Merchant, txns: list[Transaction]) -> dict:
    ids = set(m.txn_ids)
    mine = [t for t in txns if t.txn_id in ids]
    amounts = [t.amount_cents for t in mine]
    cities = Counter(c.group(0).title() for t in mine for c in CITY.finditer(t.counterparty or t.description))
    descriptions = []
    for t in mine:
        d = t.description.strip()
        if d and d not in descriptions and d != t.counterparty:
            descriptions.append(d[:80])
    return {
        "current_name": m.name,
        "statement_names": [{"name": n, "count": c} for n, c in m.raw_names.most_common(8)],
        "payments": len(mine),
        "direction": "money out" if statistics.median(amounts) < 0 else "money in",
        "payment_types": dict(Counter(t.kind for t in mine)),
        "amount_eur": {"min": _euros(min(map(abs, amounts))), "median": _euros(abs(statistics.median(amounts))),
                       "max": _euros(max(map(abs, amounts)))},
        "first": min(t.booked for t in mine).isoformat(),
        "last": max(t.booked for t in mine).isoformat(),
        "cities_in_names": dict(cities.most_common(5)),
        "sample_descriptions": descriptions[:5],
    }


class Tools:
    def __init__(self, merchant: Merchant, txns: list[Transaction], world: World):
        self.merchant, self.txns, self.world = merchant, txns, world

    def call(self, name: str, args: dict) -> dict:
        try:
            if name == "merchant_history":
                return history_summary(self.merchant, self.txns)
            if name == "search_history":
                text = str(args.get("text", "")).lower()
                hits = [t for t in self.txns if text and text in f"{t.counterparty} {t.description}".lower()]
                return {"matches": len(hits), "examples": [
                    {"date": t.booked.isoformat(), "amount_eur": _euros(t.amount_cents), "type": t.kind,
                     "name": t.counterparty, "description": t.description[:80]} for t in hits[:8]]}
            if name == "search_register":
                found = self.world.search_register(str(args.get("name", "")), args.get("city") or None)
                return {"companies": [company_dict(c) for c in found]}
            if name == "get_register_entry":
                c = self.world.register_entry(str(args.get("kvk", "")))
                return company_dict(c) if c else {"error": "no company with that registration number"}
            if name == "search_map":
                found = self.world.search_map(args.get("name") or None, args.get("street") or None, args.get("city") or None)
                return {"places": [place_dict(p) for p in found]}
        except (TypeError, ValueError) as e:
            return {"error": f"bad arguments: {e}"}
        return {"error": f"unknown tool {name}"}


@dataclass
class Finding:
    merchant_id: str
    rules_name: str
    name: str | None  # the agent's answer, None if it abstained
    category: str | None
    confidence: str | None
    evidence: list[dict] = field(default_factory=list)
    outcome: str = "named"  # named | abstained | rejected (ungrounded name) | no_answer (step limit, errors)
    steps: int = 0  # tool calls before the answer
    prompt_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0
    trace: list[dict] = field(default_factory=list)

    @property
    def citations_ok(self) -> bool:
        """Every cited step is a tool call that actually happened."""
        return all(isinstance(e.get("step"), int) and 1 <= e["step"] <= self.steps for e in self.evidence)

    @property
    def final_name(self) -> str:
        """What the merchant ends up being called: the agent's name if accepted, else the rules'."""
        return self.name if self.outcome == "named" and self.name else self.rules_name


def _grounded(name: str, texts: list[str]) -> bool:
    return any(
        fuzz.partial_ratio(name, t, processor=utils.default_process) >= 90 for t in texts if t
    )


def _case_message(m: Merchant, city: str) -> str:
    names = ", ".join(f"'{n}'" for n, _ in m.raw_names.most_common(5))
    return (
        f"Merchant to identify. Current name from the rules: '{m.name}'. "
        f"Statement names: {names}. The account holder's home city is {city or 'unknown'}."
    )


def _account(f: Finding, reply: Reply) -> None:
    f.prompt_tokens += reply.prompt_tokens
    f.output_tokens += reply.output_tokens
    f.seconds += reply.seconds


def investigate(m: Merchant, txns: list[Transaction], world: World, chat: Chat, city: str = "",
                max_steps: int = MAX_STEPS) -> Finding:
    tools = Tools(m, txns, world)
    case = _case_message(m, city)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": case}]
    f = Finding(m.id, m.name, None, None, None)
    seen = [case]  # everything the model was shown, to check its answer against
    nudged = False
    for _ in range(max_steps + 2):
        reply = chat(messages, TOOLS)
        _account(f, reply)
        messages.append(reply.raw or {"role": "assistant", "content": reply.content})
        if not reply.tool_calls:
            if nudged:
                break
            nudged = True  # small models sometimes answer in prose; ask once for the tool call
            messages.append({"role": "user", "content": "Call final_answer to give your answer."})
            continue
        for call in reply.tool_calls:
            if call.name == "final_answer":
                return _finish(f, call.arguments, seen)
            if f.steps >= max_steps:
                result = {"error": "step limit reached; call final_answer now"}
            else:
                f.steps += 1
                result = {"step": f.steps, **tools.call(call.name, call.arguments)}
                seen.append(json.dumps(result, ensure_ascii=False))
            f.trace.append({"tool": call.name, "arguments": call.arguments, "result": result})
            messages.append({"role": "tool", "content": json.dumps(result, ensure_ascii=False)})
    f.outcome = "no_answer"
    return f


def _finish(f: Finding, args: dict, seen: list[str]) -> Finding:
    name = args.get("name")
    name = name.strip() if isinstance(name, str) and name.strip().lower() not in ("", "null", "none", "unknown") else None
    category = args.get("category")
    f.name = name
    f.category = category if category in CATEGORIES else None
    f.confidence = args.get("confidence")
    f.evidence = [e for e in args.get("evidence") or [] if isinstance(e, dict)]
    f.trace.append({"tool": "final_answer", "arguments": args})
    if name is None:
        f.outcome = "abstained"
    elif not _grounded(name, seen):
        f.outcome = "rejected"
    else:
        f.outcome = "named"
    return f


BASELINE_PROMPT = """\
You identify merchants on Dutch bank statements. Given a merchant's payment history, \
give the name a customer would recognise (the shop's trade name rather than the company \
behind it) and its category. If you cannot tell, use name null. Reply with JSON only: \
{"name": string or null, "category": one of %s}\
""" % ", ".join(CATEGORIES)


def guess_without_tools(m: Merchant, txns: list[Transaction], chat: Chat, city: str = "") -> Finding:
    """The same model with the same history but no tools: does searching help at all?"""
    f = Finding(m.id, m.name, None, None, None, steps=0)
    history = json.dumps(history_summary(m, txns), ensure_ascii=False)
    messages = [
        {"role": "system", "content": BASELINE_PROMPT},
        {"role": "user", "content": f"{_case_message(m, city)}\nHistory: {history}"},
    ]
    reply = chat(messages, None)
    _account(f, reply)
    match = re.search(r"\{.*\}", reply.content, re.S)
    try:
        args = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        args = {}
    args.setdefault("confidence", None)
    return _finish(f, args, [_case_message(m, city), history])
