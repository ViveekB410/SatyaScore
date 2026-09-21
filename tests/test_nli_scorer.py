from unittest.mock import MagicMock, patch

import pytest
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


def test_score_batch_chunks_all_pairs_with_a_small_chunk_size():
    # Chunking must still return exactly one result per pair, in order, even when
    # the batch spans several chunks. Mock returns 2 rows per forward pass, so a
    # 4-pair batch with chunk_size=2 => 2 forward passes => 4 results.
    two_rows = torch.tensor([[1.0, 0.0, -1.0], [1.0, 0.0, -1.0]])
    mock_tokenizer = MagicMock()
    mock_batch = MagicMock()
    mock_batch.to.return_value = mock_batch
    mock_tokenizer.return_value = mock_batch
    mock_output = MagicMock()
    mock_output.logits = two_rows
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
            claim_ids=["c0", "c1", "c2", "c3"],
            premises=["a", "b", "c", "d"],
            hypotheses=["w", "x", "y", "z"],
            chunk_size=2,
        )

    assert [r.claim_id for r in results] == ["c0", "c1", "c2", "c3"]  # order preserved
    assert mock_model.call_count == 2  # 4 pairs / chunk_size 2 = 2 forward passes


def _real_scorer_or_skip() -> NLIScorer:
    """Load the real mDeBERTa weights, or skip if they aren't available (offline
    without a cache). The chunking-parity test needs the real attention mask."""
    scorer = NLIScorer(device="cpu")
    try:
        scorer._ensure_loaded()
    except Exception as e:  # network down / weights not cached
        pytest.skip(f"real NLI weights unavailable: {e}")
    return scorer


def test_chunked_output_matches_unchunked_within_float_noise():
    # The memory fix (chunking) must not change the numbers. On a batch with very
    # mixed premise lengths, unchunked padding (to the longest premise) differs a
    # lot from small-chunk padding; if the attention mask is doing its job, the
    # probabilities must be identical regardless of how the batch was chunked.
    scorer = _real_scorer_or_skip()
    premises = [
        "Paris is the capital of France.",
        "Water boils.",
        "The Ganges is a major river of the Indian subcontinent that rises in the "
        "western Himalayas and flows south and east through the Gangetic plain, "
        "gathering many tributaries and supporting dense populations along its "
        "entire course before emptying into the Bay of Bengal.",
        "Dogs bark.",
        "Cricket is a bat-and-ball game played between two teams of eleven players "
        "on a field at the centre of which is a twenty-two-yard pitch with a target "
        "called a wicket at each end.",
    ]
    hypotheses = [
        "France's capital is Paris.",
        "Water freezes at 100 degrees.",
        "The Ganges rises in the Himalayas.",
        "Cats bark.",
        "Cricket has eleven players per team.",
    ]
    ids = [f"c{i}" for i in range(len(premises))]

    whole = scorer.score_batch(ids, premises, hypotheses, chunk_size=len(premises))
    chunked = scorer.score_batch(ids, premises, hypotheses, chunk_size=2)

    # This checkpoint runs in fp16, so "float noise" here is ~1e-3 (probabilities
    # land on the fp16 grid), not ~1e-7: padding-length differences between chunks
    # perturb the fp16 reductions at that scale. The invariant that must hold is
    # the PREDICTED CLASS (a real masking bug would move probs by 0.1+ and flip
    # it), with probabilities agreeing to an fp16-sized tolerance.
    ATOL = 5e-3

    def _argmax(r):
        return max((("e", r.entailment_prob), ("n", r.neutral_prob),
                    ("c", r.contradiction_prob)), key=lambda t: t[1])[0]

    assert len(whole) == len(chunked) == len(premises)
    for w, c in zip(whole, chunked):
        assert w.claim_id == c.claim_id
        assert _argmax(w) == _argmax(c)  # chunking must not change the prediction
        assert abs(w.entailment_prob - c.entailment_prob) < ATOL
        assert abs(w.contradiction_prob - c.contradiction_prob) < ATOL
        assert abs(w.neutral_prob - c.neutral_prob) < ATOL
