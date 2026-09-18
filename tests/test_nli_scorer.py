from unittest.mock import MagicMock, patch

import torch

from member1_model.nli_scorer import NLIScorer


def _mock_model_and_tokenizer(logits_values):
    """Builds a fake tokenizer + model pair that returns fixed logits,
    so we can test the scoring logic without downloading real weights."""
    mock_tokenizer = MagicMock()
    mock_batch = MagicMock()
    mock_batch.to.return_value = mock_batch
    mock_tokenizer.return_value = mock_batch

    mock_output = MagicMock()
    mock_output.logits = torch.tensor([logits_values])

    mock_model = MagicMock()
    mock_model.return_value = mock_output
    mock_model.to.return_value = mock_model
    mock_model.eval.return_value = None
    mock_model.config.id2label = {0: "entailment", 1: "neutral", 2: "contradiction"}

    return mock_tokenizer, mock_model


def test_high_entailment_logit_gives_high_entailment_prob():
    mock_tokenizer, mock_model = _mock_model_and_tokenizer([10.0, 0.0, -10.0])

    with patch("member1_model.nli_scorer.AutoTokenizer") as mock_tok_cls, patch(
        "member1_model.nli_scorer.AutoModelForSequenceClassification"
    ) as mock_model_cls:
        mock_tok_cls.from_pretrained.return_value = mock_tokenizer
        mock_model_cls.from_pretrained.return_value = mock_model

        scorer = NLIScorer(device="cpu")
        result = scorer.score(
            claim_id="c1",
            premise="The Ganga originates at Gangotri glacier.",
            hypothesis="The Ganga originates in Gangotri.",
        )

    assert result.entailment_prob > 0.9
    assert result.contradiction_prob < 0.01


def test_high_contradiction_logit_gives_low_entailment_prob():
    mock_tokenizer, mock_model = _mock_model_and_tokenizer([-10.0, 0.0, 10.0])

    with patch("member1_model.nli_scorer.AutoTokenizer") as mock_tok_cls, patch(
        "member1_model.nli_scorer.AutoModelForSequenceClassification"
    ) as mock_model_cls:
        mock_tok_cls.from_pretrained.return_value = mock_tokenizer
        mock_model_cls.from_pretrained.return_value = mock_model

        scorer = NLIScorer(device="cpu")
        result = scorer.score(claim_id="c1", premise="X is true.", hypothesis="X is false.")

    assert result.contradiction_prob > 0.9
    assert result.entailment_prob < 0.01


def test_model_loaded_only_once_across_multiple_calls():
    mock_tokenizer, mock_model = _mock_model_and_tokenizer([1.0, 1.0, 1.0])

    with patch("member1_model.nli_scorer.AutoTokenizer") as mock_tok_cls, patch(
        "member1_model.nli_scorer.AutoModelForSequenceClassification"
    ) as mock_model_cls:
        mock_tok_cls.from_pretrained.return_value = mock_tokenizer
        mock_model_cls.from_pretrained.return_value = mock_model

        scorer = NLIScorer(device="cpu")
        scorer.score(claim_id="c1", premise="A", hypothesis="B")
        scorer.score(claim_id="c2", premise="C", hypothesis="D")

        assert mock_model_cls.from_pretrained.call_count == 1
        assert mock_tok_cls.from_pretrained.call_count == 1


def test_score_batch_returns_one_result_per_claim():
    # score_batch does ONE batched forward pass, so the model returns logits
    # of shape (n_pairs, 3) — mock two rows for two claims.
    mock_tokenizer = MagicMock()
    mock_batch = MagicMock()
    mock_batch.to.return_value = mock_batch
    mock_tokenizer.return_value = mock_batch

    mock_output = MagicMock()
    mock_output.logits = torch.tensor([[1.0, 1.0, 1.0], [1.0, 1.0, 1.0]])

    mock_model = MagicMock()
    mock_model.return_value = mock_output
    mock_model.to.return_value = mock_model
    mock_model.eval.return_value = None
    mock_model.config.id2label = {0: "entailment", 1: "neutral", 2: "contradiction"}

    with patch("member1_model.nli_scorer.AutoTokenizer") as mock_tok_cls, patch(
        "member1_model.nli_scorer.AutoModelForSequenceClassification"
    ) as mock_model_cls:
        mock_tok_cls.from_pretrained.return_value = mock_tokenizer
        mock_model_cls.from_pretrained.return_value = mock_model

        scorer = NLIScorer(device="cpu")
        results = scorer.score_batch(
            claim_ids=["c1", "c2"],
            premises=["A", "C"],
            hypotheses=["B", "D"],
        )

    assert len(results) == 2
    assert {r.claim_id for r in results} == {"c1", "c2"}
