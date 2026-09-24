"""Phase 2 harness: the BM25 + tokenizer used for the retrieval comparison."""
import numpy as np

from retrieval_eval import BM25, rrf, source_rank, tokenize


def test_tokenizer_keeps_devanagari_words_whole():
    # a \w+ regex would split at the vowel signs (matras); this must not
    assert tokenize("पेरिस फ्रांस की राजधानी है।") == ["पेरिस", "फ्रांस", "की", "राजधानी", "है"]
    assert tokenize("The run-out, (rule).") == ["the", "run", "out", "rule"]


def test_bm25_ranks_the_matching_document_first():
    docs = ["Paris is the capital of France.",
            "Tokyo is the capital of Japan.",
            "Dengue is spread by mosquitoes."]
    s = BM25(docs).scores("capital of Japan")
    assert int(np.argmax(s)) == 1
    assert s[2] == 0.0  # no shared terms


def test_source_rank_and_rrf():
    titles = np.array(["A", "B", "C"])
    order = np.array([[2, 0, 1], [1, 2, 0]])
    assert source_rank(order, titles, np.array(["A", "Z"])).tolist() == [2, 10**9]
    fused = rrf(np.array([[0, 1, 2]]), np.array([[0, 2, 1]]))
    assert fused[0, 0] == 0  # ranked first by both -> first after fusion
