"""
LLM verifier: a large language model judges a claim against the retrieved
evidence passages (English or Hindi) and returns a verdict plus P(claim true).

Two modes:
  grounded  judge ONLY from the passages (reproducible; limited by the corpus)
  open      passages plus the model's own knowledge (an LLM checking an LLM:
            report it as such)

Any OpenAI-compatible provider in PROVIDERS (Groq by default). The key is read from the
provider's environment variable at call time and is never printed, logged or stored. Claims and
passages are sent to that provider.
Evaluated by llm_verifier_eval.py before any use in the live pipeline.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Literal

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"
# OpenAI-compatible chat endpoints with a free tier. Each key is read from the user's own environment at
# call time; it is never printed, logged or stored. Text sent to a provider is processed by that provider
# (the Gemini and Mistral free tiers may use it to improve their models).
PROVIDERS = {
    "groq": (GROQ_URL, "GROQ_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "GEMINI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY"),
    "mistral": ("https://api.mistral.ai/v1/chat/completions", "MISTRAL_API_KEY"),
    "cerebras": ("https://api.cerebras.ai/v1/chat/completions", "CEREBRAS_API_KEY"),
    # A model on this computer (Ollama, OpenAI-compatible): no key, no quota, nothing leaves the machine.
    "ollama": ("http://localhost:11434/v1/chat/completions", None),
}
MAX_PASSAGES, MAX_PASSAGE_CHARS = 5, 600  # evidence sent per claim (free tiers are token-limited)
VERDICTS = ("Verified", "Uncertain", "Hallucinated")
Mode = Literal["grounded", "open", "crosscheck"]

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
    # Version 2 cross-check (tuned on dev): "no evidence" made the open mode call true claims Hallucinated.
    "crosscheck": ("Use the evidence passages and your own reliable knowledge. Answer Hallucinated only if "
                   "you are confident that a fact in the claim is wrong, because a passage contradicts it or "
                   "because you know the correct fact. Passages that do not mention a fact are NOT a reason "
                   "for Hallucinated. If neither the passages nor your knowledge settle it, answer Uncertain. "
                   "If the claim is vague or depends on missing context (it refers to 'this show', 'the station', "
                   "'he', 'the event' without naming them), answer Uncertain."),
}
_FORMAT = ('Reply with one JSON object and nothing else: {"verdict": "Verified" | "Uncertain" | '
           '"Hallucinated", "p_true": <probability from 0 to 1 that the claim is true>, '
           '"wrong_span": "<if Hallucinated: the exact wrong words copied from the claim, else empty>", '
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
    wrong_span: str = ""     # the wrong words, if the model gave them AND they occur in the claim


def build_messages(claim: str, passages: list[str], mode: Mode, max_passages: int = MAX_PASSAGES) -> list[dict]:
    passages = [p[:MAX_PASSAGE_CHARS] for p in passages[:max_passages]]
    evidence = "\n\n".join(f"[{i + 1}] {p}" for i, p in enumerate(passages)) or "(no passage retrieved)"
    user = f"CLAIM:\n{claim}\n\nEVIDENCE PASSAGES:\n{evidence}"
    system = f"You are a careful fact-checker.\n{_RULES}\n{_MODE_RULES[mode]}\n{_FORMAT}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


_THINK = re.compile(r"<think>.*?</think>", re.S)
_OBJECT = re.compile(r"\{.*\}", re.S)


def parse_reply(text: str, claim: str | None = None) -> LLMJudgement:
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
    span = str(obj.get("wrong_span") or "").strip()
    if not span or verdict != "Hallucinated" or (claim is not None and span not in claim):
        span = ""  # only an exact substring of the claim can be highlighted
    return LLMJudgement(verdict=verdict, p_true=p, reason=str(obj.get("reason", ""))[:300], raw=text or "",
                        wrong_span=span)


class LLMVerifier:
    MAX_RETRIES = 4
    MAX_WAIT_S = 90  # a longer Retry-After means a daily/hourly quota: stop, don't sleep
    CACHE_SIZE = 2048  # answers kept per verifier: the same claim with the same passages is not asked twice

    def __init__(self, model: str = DEFAULT_MODEL, mode: Mode = "grounded",
                 session: requests.Session | None = None, min_interval_s: float = 2.2,
                 timeout_s: float = 90, provider: str = "groq"):
        if mode not in _MODE_RULES:
            raise ValueError(f"mode must be one of {list(_MODE_RULES)}")
        if provider not in PROVIDERS:
            raise ValueError(f"provider must be one of {list(PROVIDERS)}")
        self.model, self.mode, self.provider = model, mode, provider
        self._url, self._key_var = PROVIDERS[provider]
        self._session = session or requests.Session()
        self._min_interval, self._timeout = min_interval_s, timeout_s
        self._last = 0.0
        self._lock = threading.Lock()  # verify() may be called from several threads (pipeline.llm_workers)
        self._cache: OrderedDict[tuple, LLMJudgement] = OrderedDict()
        self.tokens_used = 0
        self.max_passages = MAX_PASSAGES  # the second reading (Version 2) uses all 10 retrieved passages

    def _key(self) -> str:
        if self._key_var is None:
            return "local"
        key = os.environ.get(self._key_var, "")
        if not key:
            raise LLMVerifierError(f'{self._key_var} is not set. In PowerShell: $env:{self._key_var} = "..."')
        return key

    def _body(self, claim: str, passages: list[str]) -> dict:
        body = {"model": self.model, "messages": build_messages(claim, passages, self.mode, self.max_passages),
                "temperature": 0, "max_completion_tokens": 1024,
                "response_format": {"type": "json_object"}}
        if "gpt-oss" in self.model:  # Groq "openai/gpt-oss-20b", Ollama "gpt-oss:20b"
            body["reasoning_effort"] = "low"
        if self.provider == "gemini":
            body["max_tokens"] = body.pop("max_completion_tokens")  # Gemini's OpenAI layer uses max_tokens
        return body

    def verify(self, claim: str, passages: list[str]) -> LLMJudgement:
        key = (self.model, self.mode, claim, tuple(p[:MAX_PASSAGE_CHARS] for p in passages[:self.max_passages]))
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        j = self._verify(claim, passages)
        if j.verdict is not None:
            with self._lock:
                self._cache[key] = j
                while len(self._cache) > self.CACHE_SIZE:
                    self._cache.popitem(last=False)
        return j

    def _verify(self, claim: str, passages: list[str]) -> LLMJudgement:
        headers = {"Authorization": f"Bearer {self._key()}", "Content-Type": "application/json"}
        body = self._body(claim, passages)
        for attempt in range(self.MAX_RETRIES + 1):
            with self._lock:  # requests start at least min_interval apart, across threads
                start = max(time.monotonic(), self._last + self._min_interval)
                self._last = start
            if start > time.monotonic():
                time.sleep(start - time.monotonic())
            try:
                r = self._session.post(self._url, headers=headers, json=body, timeout=self._timeout)
            except requests.RequestException:
                if attempt == self.MAX_RETRIES:
                    raise
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 200:
                data = r.json()
                with self._lock:
                    self.tokens_used += int(data.get("usage", {}).get("total_tokens", 0))
                return parse_reply(data["choices"][0]["message"].get("content") or "", claim)
            if r.status_code in (400, 401, 403, 404):
                try:
                    err = r.json().get("error", {})
                except ValueError:
                    err = {"message": r.text[:200]}
                detail = err.get("message", "")
                if r.status_code == 400 and (err.get("code") == "json_validate_failed" or "JSON" in detail):
                    # The model's reply was not strict JSON (provider-side check). Read what it wrote with the
                    # tolerant parser; if that fails, ask once more without the strict JSON mode.
                    j = parse_reply(err.get("failed_generation") or "", claim)
                    if j.verdict is not None:
                        return j
                    if "response_format" in body:
                        body = {k: v for k, v in body.items() if k != "response_format"}
                        continue
                raise LLMVerifierError(f"{self.provider} HTTP {r.status_code}: {detail}")
            if r.status_code == 429 or r.status_code >= 500:
                retry_after = float(r.headers.get("Retry-After", 2 ** attempt) or 1)
                if retry_after > self.MAX_WAIT_S:
                    raise LLMQuotaExhausted(f"{self.provider} asks to wait {retry_after:.0f} s (rate/daily limit).")
                time.sleep(retry_after)
                continue
            raise LLMVerifierError(f"{self.provider} HTTP {r.status_code}")
        raise LLMVerifierError(f"{self.provider} did not answer after retries.")
