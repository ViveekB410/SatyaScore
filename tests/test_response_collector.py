from unittest.mock import MagicMock, patch

import pytest
import requests

from dataset_pipeline.response_collector import (
    OpenAICompatibleGenerator,
    ResponseCollector,
)


def _mock_openai_response(text: str):
    resp = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": text}}]}
    resp.raise_for_status = MagicMock()
    return resp


def test_openai_compatible_generator_parses_response():
    generator = OpenAICompatibleGenerator(
        api_key="fake-key", base_url="https://fake.example.com/v1/chat/completions", model="gpt-4"
    )
    with patch("requests.post", return_value=_mock_openai_response("India gained independence in 1947.")):
        result = generator.generate("When did India gain independence?", "en")
    assert result == "India gained independence in 1947."


def test_collector_requires_at_least_one_generator():
    with pytest.raises(ValueError):
        ResponseCollector(generators=[])


def test_collector_gathers_response_from_each_generator():
    gen_a = MagicMock()
    gen_a.model_name = "model-a"
    gen_a.generate.return_value = "Response from A."

    gen_b = MagicMock()
    gen_b.model_name = "model-b"
    gen_b.generate.return_value = "Response from B."

    collector = ResponseCollector(generators=[gen_a, gen_b])
    results = collector.collect("q1", "What is the capital of India?", "en")

    assert len(results) == 2
    assert {r.source_llm for r in results} == {"model-a", "model-b"}


def test_collector_skips_failed_generator_without_crashing():
    gen_ok = MagicMock()
    gen_ok.model_name = "model-ok"
    gen_ok.generate.return_value = "A fine response."

    gen_broken = MagicMock()
    gen_broken.model_name = "model-broken"
    gen_broken.generate.side_effect = requests.exceptions.ConnectionError("down")

    collector = ResponseCollector(generators=[gen_ok, gen_broken])
    results = collector.collect("q1", "Some query", "en")

    assert len(results) == 1
    assert results[0].source_llm == "model-ok"


def test_collect_batch_processes_multiple_queries():
    gen = MagicMock()
    gen.model_name = "model-a"
    gen.generate.return_value = "Some response."

    collector = ResponseCollector(generators=[gen])
    results = collector.collect_batch(
        [("q1", "Query one?", "en"), ("q2", "Query two?", "en")]
    )
    assert len(results) == 2
    assert {r.query_id for r in results} == {"q1", "q2"}
