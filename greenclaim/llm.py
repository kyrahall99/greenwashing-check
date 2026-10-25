"""Model client, .env loading, token accounting, and spend limits."""

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from openai import BadRequestError, OpenAI

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = REPO_ROOT / "logs" / "runs.jsonl"

# Course rule: look for .env in the repo folder first, then one level above it.
for _env in (REPO_ROOT / ".env", REPO_ROOT.parent / ".env"):
    if _env.exists():
        load_dotenv(_env)
        break

MODEL = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# Prices in USD per 1M tokens. ASSUMED placeholders: confirm against the course
# rate card before quoting costs in the report. Change them here only.
PRICE_PER_M = {"input": 0.25, "cached_input": 0.025, "output": 2.00}

# Spend limits (overspending defense).
MAX_INPUT_CHARS = 20_000      # longer documents are refused before any model call
MAX_CALLS_PER_RUN = 6         # one review uses 4 calls; anything above this is a bug
MAX_TOKENS_PER_RUN = 60_000   # hard stop on total tokens for one review
MAX_OUTPUT_TOKENS = 4_000     # cap on each model response


class BudgetExceeded(RuntimeError):
    """Raised when a review would go over its call or token budget."""


class ProviderBlocked(RuntimeError):
    """Raised when the model provider's content filter refuses the prompt."""


def make_client() -> OpenAI:
    """Prefer the course Portkey key; fall back to a personal OpenAI key."""
    portkey = os.getenv("PORTKEY_API_KEY")
    if portkey:
        return OpenAI(
            base_url=PORTKEY_BASE_URL,
            api_key="portkey",  # unused; Portkey authenticates with the header
            default_headers={
                "x-portkey-api-key": portkey,
                # Skip Portkey's whole-response cache so every review is a real model run
                # with real token counts. Prompt (prefix) caching still applies.
                "x-portkey-cache-force-refresh": "true",
            },
        )
    if os.getenv("OPENAI_API_KEY"):
        return OpenAI()
    raise RuntimeError(
        "No API key found. Put PORTKEY_API_KEY in a .env file in this folder "
        "or in the folder one level above it (see .env.example)."
    )


@dataclass
class Usage:
    """Token counts and cost for one review, broken down by agent."""

    steps: list = field(default_factory=list)

    def add(self, agent: str, usage, seconds: float, replay: bool = False) -> None:
        details = getattr(usage, "prompt_tokens_details", None)
        cached = (getattr(details, "cached_tokens", 0) or 0) if details else 0
        if replay:
            # Portkey answered from its response cache: no model ran, nothing billed.
            # It copies the original usage numbers, so record zeros instead.
            self.steps.append({"agent": agent, "input": 0, "cached_input": 0, "output": 0,
                               "seconds": round(seconds, 2), "replayed": True})
            return
        self.steps.append({
            "agent": agent,
            "input": usage.prompt_tokens - cached,
            "cached_input": cached,
            "output": usage.completion_tokens,
            "seconds": round(seconds, 2),
        })

    def total(self, key: str) -> int:
        return sum(s[key] for s in self.steps)

    @property
    def total_tokens(self) -> int:
        return self.total("input") + self.total("cached_input") + self.total("output")

    @property
    def cost(self) -> float:
        return sum(self.total(k) * PRICE_PER_M[k] / 1_000_000 for k in PRICE_PER_M)

    def summary(self) -> dict:
        return {
            "calls": len(self.steps),
            "input": self.total("input"),
            "cached_input": self.total("cached_input"),
            "output": self.total("output"),
            "cost_usd": round(self.cost, 6),
            "seconds": round(sum(s["seconds"] for s in self.steps), 2),
            "replayed_calls": sum(1 for s in self.steps if s.get("replayed")),
            "steps": self.steps,
        }


class LLM:
    """Wraps the client so every call is counted and checked against the budget."""

    def __init__(self, client: OpenAI | None = None):
        self.client = client or make_client()
        self.usage = Usage()

    def _create(self, system: str, user: str, agent: str):
        return self.client.chat.completions.with_raw_response.create(
            model=MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            max_completion_tokens=MAX_OUTPUT_TOKENS,
            prompt_cache_key=f"greenclaim-{agent}",  # route repeat prompts to the same cache
        )

    def json_call(self, agent: str, system: str, user: str) -> dict:
        if len(self.usage.steps) >= MAX_CALLS_PER_RUN:
            raise BudgetExceeded(f"Call limit of {MAX_CALLS_PER_RUN} reached before {agent}.")
        if self.usage.total_tokens >= MAX_TOKENS_PER_RUN:
            raise BudgetExceeded(f"Token limit of {MAX_TOKENS_PER_RUN:,} reached before {agent}.")
        start = time.time()
        try:
            raw = self._create(system, user, agent)
        except BadRequestError as e:
            if "content_filter" in str(e) or "content management policy" in str(e):
                self.usage.steps.append({"agent": agent, "input": 0, "cached_input": 0, "output": 0,
                                         "seconds": round(time.time() - start, 2), "blocked": True})
                raise ProviderBlocked(
                    f"The model provider's content filter blocked the {agent} step, most likely "
                    "because the document contains text that tries to manipulate the AI."
                ) from e
            raise
        resp = raw.parse()

        replay = raw.headers.get("x-portkey-cache-status", "").upper() in ("HIT", "SEMANTIC HIT")
        self.usage.add(agent, resp.usage, time.time() - start, replay)
        try:
            return json.loads(resp.choices[0].message.content or "{}")
        except json.JSONDecodeError:
            return {}


def log_run(record: dict) -> None:
    LOG_PATH.parent.mkdir(exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(record) + "\n")
