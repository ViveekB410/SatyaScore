"""
LLM verifier: a large language model judges a claim against the retrieved
evidence passages (English or Hindi) and returns a verdict plus P(claim true).

Two modes:
  grounded  judge ONLY from the passages (reproducible; limited by the corpus)
  open      passages plus the model's own knowledge (an LLM checking an LLM:
            report it as such)

Groq's OpenAI-compatible API. The key is read from GROQ_API_KEY at call time and
is never printed, logged or stored. Claims and passages are sent to Groq.
Evaluated by llm_verifier_eval.py before any use in the live pipeline.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Literal

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"
VERDICTS = ("Verified", "Uncertain", "Hallucinated")
Mode = Literal["grounded", "open"]

_RULES = (
    "Verdicts:\n"
    "- Verified: every fact in the claim is correct.\n"
    "- Hallucinated: at least one fact in the claim is wrong (the worst fact decides).\n"
    "- Uncertain: you cannot tell whether it is correct.\n"
    "A claim that is partly right and partly wrong is Hallucinated. Judge the meaning, not "
    "the language: the claim and the passages may be in Hindi or English."
)
_MODE_RULES = {
    "grounded": ("Use ONLY the evidence passages. Do not use outside knowledge. If the passages do "
                 "not state or directly imply the facts, answer Uncertain; answer Hallucinated only "
                 "if the passages contradict the claim."),
    "open": ("Use the evidence passages and your own reliable knowledge. Answer Uncertain only if "
             "you genuinely cannot tell."),
}
_FORMAT = ('Reply with one JSON object and nothing else: {"verdict": "Verified" | "Uncertain" | '
           '"Hallucinated", "p_true": <probability from 0 to 1 that the claim is true>, '
           '"reason": "<one short sentence>"}')


class LLMVerifierError(RuntimeError):
    """Configuration or API failure that retrying will not fix (bad key, no access)."""


class LLMQuotaExhausted(RuntimeError):
    """The provider asked us to wait longer than MAX_WAIT_S (e.g. a daily limit)."""


@dataclass
class LLMJudgement:
    verdict: str | None      # one of VERDICTS, or None if the reply could not be parsed
    p_true: float | None     # 0..1
    reason: str
    raw: str


def build_messages(claim: str, passages: list[str], mode: Mode) -> list[dict]:
    evidence = "\n\n".join(f"[{i + 1}] {p}" for i, p in enumerate(passages)) or "(no passage retrieved)"
    user = f"CLAIM:\n{claim}\n\nEVIDENCE PASSAGES:\n{evidence}"
    system = f"You are a careful fact-checker.\n{_RULES}\n{_MODE_RULES[mode]}\n{_FORMAT}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


_THINK = re.compile(r"<think>.*?</think>", re.S)
_OBJECT = re.compile(r"\{.*\}", re.S)


def parse_reply(text: str) -> LLMJudgement:
    """Tolerant parse: strips reasoning blocks, takes the JSON object, validates it.
    p_true falls back to the verdict (1 / 0.5 / 0) if missing or invalid."""
    clean = _THINK.sub("", text or "").strip()
    m = _OBJECT.search(clean)
    try:
        obj = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        obj = {}
    verdict = obj.get("verdict")
    verdict = next((v for v in VERDICTS if isinstance(verdict, str) and verdict.strip().lower() == v.lower()), None)
    try:
        p = float(obj.get("p_true"))
        p = min(1.0, max(0.0, p)) if p == p else None  # NaN -> None
    except (TypeError, ValueError):
        p = None
    if p is None and verdict is not None:
        p = {"Verified": 1.0, "Uncertain": 0.5, "Hallucinated": 0.0}[verdict]
    return LLMJudgement(verdict=verdict, p_true=p, reason=str(obj.get("reason", ""))[:300], raw=text or "")


class LLMVerifier:
    MAX_RETRIES = 4
    MAX_WAIT_S = 90  # a longer Retry-After means a daily/hourly quota: stop, don't sleep

    def __init__(self, model: str = DEFAULT_MODEL, mode: Mode = "grounded",
                 session: requests.Session | None = None, min_interval_s: float = 2.2,
                 timeout_s: float = 90):
        if mode not in _MODE_RULES:
            raise ValueError(f"mode must be one of {list(_MODE_RULES)}")
        self.model, self.mode = model, mode
        self._session = session or requests.Session()
        self._min_interval, self._timeout = min_interval_s, timeout_s
        self._last = 0.0
        self.tokens_used = 0

    @staticmethod
    def _key() -> str:
        key = os.environ.get("GROQ_API_KEY", "")
        if not key:
            raise LLMVerifierError('GROQ_API_KEY is not set. In PowerShell: $env:GROQ_API_KEY = "gsk_..."')
        return key

    def _body(self, claim: str, passages: list[str]) -> dict:
        body = {"model": self.model, "messages": build_messages(claim, passages, self.mode),
                "temperature": 0, "max_completion_tokens": 1024,
                "response_format": {"type": "json_object"}}
        if self.model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"
        return body

    def verify(self, claim: str, passages: list[str]) -> LLMJudgement:
        headers = {"Authorization": f"Bearer {self._key()}", "Content-Type": "application/json"}
        body = self._body(claim, passages)
        for attempt in range(self.MAX_RETRIES + 1):
            wait = self._min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                r = self._session.post(GROQ_URL, headers=headers, json=body, timeout=self._timeout)
            except requests.RequestException:
                if attempt == self.MAX_RETRIES:
                    raise
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 200:
                data = r.json()
                self.tokens_used += int(data.get("usage", {}).get("total_tokens", 0))
                return parse_reply(data["choices"][0]["message"].get("content") or "")
            if r.status_code in (400, 401, 403, 404):
                try:
                    detail = r.json().get("error", {}).get("message", "")
                except ValueError:
                    detail = r.text[:200]
                raise LLMVerifierError(f"Groq HTTP {r.status_code}: {detail}")
            if r.status_code == 429 or r.status_code >= 500:
                retry_after = float(r.headers.get("Retry-After", 2 ** attempt) or 1)
                if retry_after > self.MAX_WAIT_S:
                    raise LLMQuotaExhausted(f"Groq asks to wait {retry_after:.0f} s (rate/daily limit).")
                time.sleep(retry_after)
                continue
            raise LLMVerifierError(f"Groq HTTP {r.status_code}")
        raise LLMVerifierError("Groq did not answer after retries.")
