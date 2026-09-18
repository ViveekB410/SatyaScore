"""
Collects LLM responses to seed queries.

PRD ref: Section 11.2 Step 2 — "Feed queries to GPT-4, Llama 3, and
Gemini. Each generates a multi-sentence response = potential
hallucinations."

HONESTY NOTE: I don't have API keys for GPT-4/Llama-3/Gemini available to
test this against live endpoints, so `OpenAICompatibleGenerator` below is
written correctly (standard chat-completions request/response shape) but
UNTESTED against a real API in this environment — only tested here via
mocked HTTP responses. Many providers (OpenAI itself, Groq, Together AI,
local vLLM/Ollama servers, and others) speak this same OpenAI-compatible
format, so one implementation covers a lot of ground — just point
`base_url` at whichever provider you actually have a key for. Confirm it
works with one real query before running it across your full query bank.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import requests


@dataclass
class LLMResponse:
    query_id: str
    query_text: str
    response_text: str
    source_llm: str
    latency_ms: float


class ResponseGenerator(ABC):
    """Interface every LLM backend implements — makes the collector
    provider-agnostic (Section 11.2 Step 2 names 3 different LLMs)."""

    @abstractmethod
    def generate(self, query_text: str, language: str) -> str:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...


class OpenAICompatibleGenerator(ResponseGenerator):
    """
    Works with any provider exposing an OpenAI-compatible /chat/completions
    endpoint: OpenAI itself, Groq, Together AI, Fireworks, local
    Ollama/vLLM servers, etc. Point `base_url` and `model` at whichever
    one you have access to.

    Usage:
        gen = OpenAICompatibleGenerator(
            api_key="sk-...",
            base_url="https://api.openai.com/v1/chat/completions",
            model="gpt-4",
        )
        response_text = gen.generate("When did India gain independence?", "en")
    """

    def __init__(self, api_key: str, base_url: str, model: str, timeout: int = 30):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    @property
    def model_name(self) -> str:
        return self.model

    def generate(self, query_text: str, language: str) -> str:
        lang_instruction = {
            "en": "Answer in English.",
            "hi": "उत्तर हिंदी में दें।",
            "mr": "मराठीत उत्तर द्या.",
        }.get(language, "Answer in English.")

        response = requests.post(
            self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": f"Answer factually and concisely. {lang_instruction}"},
                    {"role": "user", "content": query_text},
                ],
                "temperature": 0.7,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


class ResponseCollector:
    def __init__(self, generators: list[ResponseGenerator]):
        """Takes MULTIPLE generators — Section 11.2 Step 2 explicitly wants
        responses from more than one LLM (GPT-4, Llama-3, Gemini), since
        different models hallucinate differently and a dataset built from
        only one model's outputs would bias the benchmark."""
        if not generators:
            raise ValueError("At least one ResponseGenerator is required")
        self.generators = generators

    def collect(self, query_id: str, query_text: str, language: str) -> list[LLMResponse]:
        """Runs the query through every configured generator, returning one
        LLMResponse per model (so the same query contributes multiple
        independent potential-hallucination samples)."""
        results = []
        for generator in self.generators:
            start = time.perf_counter()
            try:
                text = generator.generate(query_text, language)
            except requests.RequestException as e:
                # Don't let one provider's outage kill the whole collection
                # run — skip it and keep going with the others.
                continue
            latency_ms = (time.perf_counter() - start) * 1000
            results.append(
                LLMResponse(
                    query_id=query_id,
                    query_text=query_text,
                    response_text=text,
                    source_llm=generator.model_name,
                    latency_ms=latency_ms,
                )
            )
        return results

    def collect_batch(self, queries: list[tuple[str, str, str]]) -> list[LLMResponse]:
        """queries: list of (query_id, query_text, language) tuples."""
        all_results = []
        for query_id, query_text, language in queries:
            all_results.extend(self.collect(query_id, query_text, language))
        return all_results
