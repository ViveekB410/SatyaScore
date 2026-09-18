import csv
from unittest.mock import MagicMock

import pytest

from dataset_pipeline.dataset_builder import DatasetBuilder, CSV_COLUMNS
from dataset_pipeline.response_collector import LLMResponse
from member1_model.cmhsa import ClaimSubScores


def _mock_pipeline_result(claims, sub_scores):
    result = MagicMock()
    result.claims = claims
    result.sub_scores = sub_scores
    return result


def test_build_rows_from_response():
    pipeline = MagicMock()
    pipeline.run.return_value = _mock_pipeline_result(
        claims=["India gained independence in 1947.", "Nehru was the first PM."],
        sub_scores=[
            ClaimSubScores("claim_0", sem_sim=0.9, nli_prob=0.85, kg_conf=0.8),
            ClaimSubScores("claim_1", sem_sim=0.7, nli_prob=None, kg_conf=None),
        ],
    )
    builder = DatasetBuilder(pipeline)
    response = LLMResponse(
        query_id="history_en_00",
        query_text="When did India gain independence?",
        response_text="India gained independence in 1947. Nehru was the first PM.",
        source_llm="gpt-4",
        latency_ms=100.0,
    )
    rows = builder.build_rows_from_response(response, language="en", domain="history")

    assert len(rows) == 2
    assert rows[0].sem_sim == 0.9
    assert rows[1].nli_prob is None
    assert rows[0].source_llm == "gpt-4"
    assert rows[0].domain == "history"


def test_build_rows_returns_empty_when_no_claims_extractable():
    pipeline = MagicMock()
    pipeline.run.side_effect = ValueError("No claims could be extracted")
    builder = DatasetBuilder(pipeline)
    response = LLMResponse("q1", "query", "...", "gpt-4", 10.0)

    rows = builder.build_rows_from_response(response, language="en", domain="history")
    assert rows == []


def test_export_csv_writes_expected_columns(tmp_path):
    pipeline = MagicMock()
    pipeline.run.return_value = _mock_pipeline_result(
        claims=["Delhi is the capital of India."],
        sub_scores=[ClaimSubScores("claim_0", sem_sim=0.95, nli_prob=0.9, kg_conf=0.85)],
    )
    builder = DatasetBuilder(pipeline)
    response = LLMResponse("gov_en_00", "What is the capital?", "Delhi is the capital of India.", "gpt-4", 50.0)
    rows = builder.build_rows_from_response(response, language="en", domain="government")

    output_path = tmp_path / "dataset.csv"
    builder.export_csv(rows, output_path)

    with open(output_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == CSV_COLUMNS
        written_rows = list(reader)

    assert len(written_rows) == 1
    assert written_rows[0]["claim_text"] == "Delhi is the capital of India."
    assert written_rows[0]["gold_verdict"] == ""  # blank, awaiting human annotation
    assert written_rows[0]["sem_sim"] == "0.95"


def test_to_training_csv_keeps_annotated_rows_with_partial_signals(tmp_path):
    annotated_path = tmp_path / "annotated.csv"
    with open(annotated_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        # Row 1: fully annotated, complete signals — included.
        writer.writerow(
            {
                "claim_id": "c1", "source_query_id": "q1", "source_llm": "gpt-4", "language": "en",
                "domain": "history", "claim_text": "text1", "sem_sim": "0.9", "nli_prob": "0.85",
                "kg_conf": "0.8", "gold_verdict": "Verified", "evidence_url": "http://example.com",
            }
        )
        # Row 2: not yet annotated — excluded (no gold_verdict).
        writer.writerow(
            {
                "claim_id": "c2", "source_query_id": "q1", "source_llm": "gpt-4", "language": "en",
                "domain": "history", "claim_text": "text2", "sem_sim": "0.5", "nli_prob": "0.5",
                "kg_conf": "0.5", "gold_verdict": "", "evidence_url": "",
            }
        )
        # Row 3: annotated, kg_conf blank but sem_sim+nli_prob present — KEPT.
        # kg_conf is blank on ~100% of real rows; train_weights.py masks it and
        # renormalises the remaining weights, so dropping this row would throw
        # away almost the entire training set. The blank must be PRESERVED, not
        # fabricated into a 0.0.
        writer.writerow(
            {
                "claim_id": "c3", "source_query_id": "q1", "source_llm": "gpt-4", "language": "en",
                "domain": "history", "claim_text": "text3", "sem_sim": "0.5", "nli_prob": "0.5",
                "kg_conf": "", "gold_verdict": "Hallucinated", "evidence_url": "http://example.com",
            }
        )
        # Row 4: annotated but NO signal at all — excluded (nothing to learn).
        writer.writerow(
            {
                "claim_id": "c4", "source_query_id": "q1", "source_llm": "gpt-4", "language": "en",
                "domain": "history", "claim_text": "text4", "sem_sim": "", "nli_prob": "",
                "kg_conf": "", "gold_verdict": "Verified", "evidence_url": "",
            }
        )

    training_path = tmp_path / "training.csv"
    written = DatasetBuilder.to_training_csv(annotated_path, training_path)

    assert written == 2
    with open(training_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_id = {r["claim_id"]: r for r in rows}
    assert set(by_id) == {"c1", "c3"}
    assert by_id["c1"]["gold_verdict"] == "Verified"
    # The partial row is kept with its missing signal preserved as a blank.
    assert by_id["c3"]["gold_verdict"] == "Hallucinated"
    assert by_id["c3"]["kg_conf"] == ""
