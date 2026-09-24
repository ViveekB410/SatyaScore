"""Round-3 KG relational pilot: generation filter and pre-registered analysis."""
import json

import numpy as np
import pandas as pd
import pytest


def test_hallucinated_f1_uses_the_shipped_cutoff():
    from analyze_round3 import hallu_f1
    y = np.array([1, 1, 0, 0])              # 1 = Verified
    assert hallu_f1(y, np.array([0.9, 0.8, 0.1, 0.2])) == 1.0
    assert hallu_f1(y, np.array([0.9, 0.8, 0.5, 0.6])) == 0.0  # Uncertain is not a Hallucinated call


def test_generate_keeps_only_relational_claims(tmp_path, monkeypatch):
    pytest.importorskip("openpyxl")
    import round3_generate as g
    (tmp_path / "questions.json").write_text(json.dumps([
        {"id": "q01", "relation": "born in", "question": "Where was X born?"},
        {"id": "q02", "relation": "is the capital of", "question": "Capital?"}]), encoding="utf-8")
    monkeypatch.setattr(g, "OUT", tmp_path)
    monkeypatch.setattr(g, "RAW", tmp_path / "raw.json")
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(g, "DELAY_S", 0)
    answers = {"Where was X born?": "Srinivasa Ramanujan was born in Erode. He loved numbers.",
               "Capital?": "Kohima is the capital of Nagaland. It is a hill town."}
    monkeypatch.setattr(g.OpenAICompatibleGenerator, "generate", lambda self, q, lang: answers[q])
    g.main()
    df = pd.read_csv(tmp_path / "claims_round3.csv")
    assert set(df.relation_phrase) == {"was born in", "is the capital of"}  # longest phrase wins
    assert not df.claim_text.str.contains("loved numbers|hill town").any()  # non-relational dropped
    sheet = pd.read_excel(tmp_path / "round3_annotator_A.xlsx")
    assert list(sheet.columns) == g.COLS and sheet.verdict.isna().all()  # blind
    # a re-run resumes from the checkpoint and asks nothing again
    monkeypatch.setattr(g.OpenAICompatibleGenerator, "generate",
                        lambda *a: (_ for _ in ()).throw(AssertionError("re-asked")))
    g.main()


def test_analysis_detects_a_perfect_kg_and_applies_the_positive_floor(tmp_path, monkeypatch):
    pytest.importorskip("openpyxl")
    import analyze_round3 as a
    rng = np.random.default_rng(0)
    n = 40
    labels = ["Verified"] * 20 + ["Hallucinated"] * 20
    ids = [f"c{i}" for i in range(n)]
    sheet = pd.DataFrame({"claim_id": ids, "verdict": labels})
    for tag in ("A", "B"):
        sheet.to_excel(tmp_path / f"round3_annotator_{tag}.xlsx", index=False)
    pd.DataFrame({
        "claim_id": ids, "claim_text": ids, "relation_phrase": "born in",
        "nli_net": rng.uniform(0.3, 0.7, n),            # uninformative NLI
        "contra_top1": rng.uniform(0, 1, n), "top1_sim": 0.5,
        "kg_conf": [1.0] * 20 + [0.0] * 20,              # perfect KG
        "kg_status": ["supported"] * 20 + ["contradicted"] * 20,
    }).to_csv(tmp_path / "signals_round3.csv", index=False)
    monkeypatch.setattr(a, "OUT", tmp_path)
    monkeypatch.setattr(a, "ROOT", tmp_path)
    (tmp_path / "results").mkdir()
    a.main()
    report = (tmp_path / "results" / "round3_kg_pilot.md").read_text(encoding="utf-8")
    assert "KG helps on relational claims" in report
    assert "Too few positives" not in report
    assert "KG **supported** → gold Verified: 20/20" in report
