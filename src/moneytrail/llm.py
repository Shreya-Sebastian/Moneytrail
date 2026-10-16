"""Minimal client for a local Ollama server, so nothing leaves the machine.

Only the chat endpoint is used. Requests are deterministic (temperature 0, fixed seed)
so evaluation runs can be repeated.
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

DEFAULT_MODEL = "qwen3:8b"
DEFAULT_HOST = "http://127.0.0.1:11434"


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class Reply:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0
    raw: dict = field(default_factory=dict)  # the assistant message, to append to the history as is


class Chat(Protocol):
    def __call__(self, messages: list[dict], tools: list[dict] | None = None) -> Reply: ...


class Ollama:
    def __init__(self, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST, think: bool = False,
                 num_ctx: int = 8192, timeout: float = 300):
        self.model, self.host, self.think, self.num_ctx, self.timeout = model, host, think, num_ctx, timeout

    def __call__(self, messages: list[dict], tools: list[dict] | None = None) -> Reply:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": self.think,
            "options": {"temperature": 0, "seed": 0, "num_ctx": self.num_ctx},
        }
        if tools:
            body["tools"] = tools
        req = urllib.request.Request(
            f"{self.host}/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
        )
        start = time.perf_counter()
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read())
        msg = data["message"]
        calls = []
        for c in msg.get("tool_calls") or []:
            args = c["function"].get("arguments") or {}
            if isinstance(args, str):
                args = json.loads(args or "{}")
            calls.append(ToolCall(c["function"]["name"], args))
        return Reply(
            content=msg.get("content", ""),
            tool_calls=calls,
            prompt_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            seconds=time.perf_counter() - start,
            raw={k: msg[k] for k in ("role", "content", "tool_calls") if k in msg},
        )
