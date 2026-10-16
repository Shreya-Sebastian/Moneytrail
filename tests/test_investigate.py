"""The investigator's loop and safeguards, with a scripted model in place of a real one."""

from collections import Counter
from datetime import date

from moneytrail.investigate import guess_without_tools, home_city, investigate, needs_investigation
from moneytrail.llm import Reply, ToolCall
from moneytrail.merchants import Merchant
from moneytrail.model import Transaction
from moneytrail.world import World, build_world
from moneytrail.synth.world_dev import COMPANIES, PLACES


def _txn(i: int, name: str, cents: int = -450, kind: str = "card") -> Transaction:
    return Transaction(f"t{i}", "ing", "NL00", date(2026, 1, 1 + i % 28), cents, kind, name, "", "", "f", i)


TXNS = [_txn(i, "CCV*JV HOLDING B.V.") for i in range(4)] + [_txn(10 + i, "AH 1234 UTRECHT") for i in range(3)]
MERCHANT = Merchant("jv-holding", "JV Holding", [f"t{i}" for i in range(4)], Counter({"CCV*JV HOLDING B.V.": 4}))
WORLD = World(list(COMPANIES), list(PLACES))


class Scripted:
    """Plays back a fixed list of replies and records what it was sent."""

    def __init__(self, *replies: Reply):
        self.replies, self.sent = list(replies), []

    def __call__(self, messages, tools=None):
        self.sent.append(list(messages))
        return self.replies.pop(0)


def _calls(*calls: tuple[str, dict]) -> Reply:
    return Reply("", [ToolCall(n, a) for n, a in calls], prompt_tokens=10, output_tokens=5, seconds=0.1)


def _answer(name, step=2) -> Reply:
    return _calls(("final_answer", {"name": name, "category": "eating_out", "confidence": "high",
                                    "evidence": [{"step": step, "fact": "trade name"}]}))


def test_gate_picks_legal_entities():
    assert needs_investigation(MERCHANT)
    assert not needs_investigation(Merchant("ah", "Albert Heijn", [], Counter({"AH 1234 UTRECHT": 3})))


def test_home_city():
    assert home_city(TXNS) == "Utrecht"


def test_register_search_returns_lookalikes():
    names = [c.legal_name for c in WORLD.search_register("JV HOLDING")]
    assert "JV Holding B.V." in names and "JV Holding Amsterdam B.V." in names
    assert [c.legal_name for c in WORLD.search_register("JV Holding", city="Utrecht")] == ["JV Holding B.V."]


def test_agent_names_merchant_from_tool_results():
    chat = Scripted(
        _calls(("search_register", {"name": "JV Holding B.V.", "city": "Utrecht"})),
        _calls(("search_map", {"street": "Oudegracht 112", "city": "Utrecht"})),
        _answer("Cafe Jansz"),
    )
    f = investigate(MERCHANT, TXNS, WORLD, chat, "Utrecht")
    assert f.outcome == "named" and f.final_name == "Cafe Jansz"
    assert f.steps == 2 and f.citations_ok
    assert f.prompt_tokens == 30
    # each tool result went back to the model, numbered
    assert '"step": 2' in chat.sent[2][-1]["content"]


def test_made_up_name_is_rejected():
    chat = Scripted(_calls(("merchant_history", {})), _answer("Koffiehuis Utrecht", step=1))
    f = investigate(MERCHANT, TXNS, WORLD, chat, "Utrecht")
    assert f.outcome == "rejected" and f.final_name == "JV Holding"


def test_abstaining_keeps_rules_name():
    chat = Scripted(_answer(None, step=0))
    f = investigate(MERCHANT, TXNS, WORLD, chat)
    assert f.outcome == "abstained" and f.final_name == "JV Holding"


def test_citing_a_step_that_never_happened_is_flagged():
    chat = Scripted(_calls(("search_register", {"name": "JV Holding"})), _answer("Cafe Jansz", step=5))
    f = investigate(MERCHANT, TXNS, WORLD, chat)
    assert f.outcome == "named" and not f.citations_ok


def test_step_limit():
    looping = [_calls(("merchant_history", {})) for _ in range(12)]
    f = investigate(MERCHANT, TXNS, WORLD, Scripted(*looping), max_steps=3)
    assert f.steps == 3 and f.outcome == "no_answer"
    assert any("step limit" in str(t["result"]) for t in f.trace)


def test_prose_answer_gets_one_nudge():
    chat = Scripted(Reply("It is probably a cafe."), _answer(None))
    f = investigate(MERCHANT, TXNS, WORLD, chat)
    assert f.outcome == "abstained"
    assert "final_answer" in chat.sent[1][-1]["content"]


def test_bad_tool_arguments_do_not_crash():
    chat = Scripted(_calls(("get_register_entry", {"kvk": None}), ("nonsense", {})), _answer(None))
    f = investigate(MERCHANT, TXNS, WORLD, chat)
    assert [t["result"].get("error") is not None for t in f.trace[:2]] == [True, True]


def test_baseline_parses_json_and_is_grounded():
    f = guess_without_tools(MERCHANT, TXNS, Scripted(Reply('{"name": "Cafe Jansz", "category": "eating_out"}')))
    assert f.outcome == "rejected"  # nothing it was shown says "Cafe Jansz"
    f = guess_without_tools(MERCHANT, TXNS, Scripted(Reply('Sure: {"name": "JV Holding", "category": "shopping"}')))
    assert f.outcome == "named" and f.category == "shopping"


def test_worlds_cover_every_hard_merchant():
    from moneytrail.synth import load_catalog

    for set_name in ("dev", "heldout"):
        world = build_world(set_name)
        trade_names = {n for c in world.companies for n in c.trade_names}
        hard = [m.name for m in load_catalog(set_name).MERCHANTS.values() if m.hard]
        assert all(n in trade_names for n in hard), set_name
