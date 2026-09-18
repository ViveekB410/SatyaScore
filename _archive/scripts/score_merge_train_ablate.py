"""
score_merge_train_ablate.py — End-to-end: score synthetic claims, merge into
gold dataset, retrain weights, and run ablation.

Steps:
  2. Build evidence corpus + score synthetic claims (sem_sim, nli_prob)
  3. Merge synthetics into gold CSV v3, rebuild train/test splits
  4. Train weights (with and without SemSim)
  5. Run ablation on held-out test set
  6. Print results tables

Run:
    python score_merge_train_ablate.py
"""

from __future__ import annotations

import csv
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, classification_report
from sklearn.model_selection import train_test_split

# ── Step 2: Score synthetic claims ──────────────────────────────────────

SYNTHETIC_CSV = Path("synthetic_hallucinations.csv")
GOLD_V2_CSV = Path("SatyaScore_final_gold_456claims_v2.csv")
GOLD_V3_CSV = Path("SatyaScore_final_gold_v3_balanced.csv")
TRAIN_CSV = Path("gold_train_v3.csv")
TEST_CSV = Path("gold_test_v3.csv")
RESULTS_DIR = Path("results")

# Same topics as generate_dataset.py
STARTER_TOPICS_EN = [
    "Dengue_fever", "Immune_system", "Paracetamol", "Type_2_diabetes",
    "Tuberculosis", "Vaccination", "Hypertension", "Insulin",
    "Indian_independence_movement", "Jawaharlal_Nehru", "World_War_I",
    "Constitution_of_India", "Mughal_Empire", "Dandi_March",
    "Battle_of_Plassey", "Shivaji", "Non-cooperation_movement", "United_Nations",
    "Water", "Photosynthesis", "Season", "Speed_of_light", "Vaccine",
    "Mass_versus_weight", "Greenhouse_effect", "Plate_tectonics",
    "Black_hole", "DNA",
    "President_of_India", "Fundamental_rights_in_India", "Lok_Sabha",
    "Election_Commission_of_India", "Rajya_Sabha", "Chief_Minister_(India)",
    "Reserve_Bank_of_India", "Governor_(India)", "Article_370",
    "Cricket", "Cricket_World_Cup", "India_men's_national_field_hockey_team",
    "Offside_(association_football)", "Indian_Premier_League",
    "Ranji_Trophy", "Formula_One",
]

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
MAX_CHUNK_CHARS = 400
MIN_CHUNK_CHARS = 40


def _chunk_article_text(text: str) -> list[str]:
    """Split article into ~400-char chunks at paragraph/sentence boundaries."""
    chunks = []
    for para in _PARAGRAPH_SPLIT.split(text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= MAX_CHUNK_CHARS:
            if len(para) >= MIN_CHUNK_CHARS:
                chunks.append(para)
            continue
        sentences = _SENTENCE_SPLIT.split(para)
        current = ""
        for sent in sentences:
            if len(current) + len(sent) + 1 > MAX_CHUNK_CHARS:
                if len(current) >= MIN_CHUNK_CHARS:
                    chunks.append(current.strip())
                current = sent
            else:
                current = current + " " + sent if current else sent
        if len(current) >= MIN_CHUNK_CHARS:
            chunks.append(current.strip())
    return chunks


def fetch_wikipedia_fulltext(title: str) -> str | None:
    """Fetch full article text from Wikipedia API."""
    import requests
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query", "titles": title, "prop": "extracts",
        "explaintext": "1", "format": "json",
    }
    for attempt in range(3):
        try:
            r = requests.get(url, params=params,
                           headers={"User-Agent": "SatyaScore/1.0"},
                           timeout=15)
            r.raise_for_status()
            pages = r.json().get("query", {}).get("pages", {})
            for page in pages.values():
                text = page.get("extract", "")
                if text and len(text) > 100:
                    return text
        except Exception as e:
            print(f"  [fetch] attempt {attempt+1} failed for {title}: {e}")
            time.sleep(2 ** attempt)
    return None


def build_corpus_and_score(synthetic_csv: Path) -> pd.DataFrame:
    """Build evidence corpus, score synthetic claims through the pipeline."""
    print("\n" + "=" * 70)
    print("STEP 2: Scoring synthetic claims through the pipeline")
    print("=" * 70)

    # Load synthetic claims
    synth_df = pd.read_csv(synthetic_csv)
    print(f"Loaded {len(synth_df)} synthetic claims from {synthetic_csv}")

    # ── Load ML components ──
    print("\nLoading models (this may take a few minutes on first run)...")

    from member1_model.embeddings import CrossLingualEmbedder
    from member1_model.nli_scorer import NLIScorer
    from member3_backend.faiss_retriever import FAISSRetriever

    embedder = CrossLingualEmbedder()
    nli_scorer = NLIScorer()
    retriever = FAISSRetriever()

    # ── Build evidence corpus ──
    print("\nFetching Wikipedia articles for evidence corpus...")
    all_ids, all_texts = [], []
    for i, topic in enumerate(STARTER_TOPICS_EN):
        text = fetch_wikipedia_fulltext(topic)
        if text:
            chunks = _chunk_article_text(text)
            for j, chunk in enumerate(chunks):
                all_ids.append(f"{topic}_{j}")
                all_texts.append(chunk)
            print(f"  [{i+1}/{len(STARTER_TOPICS_EN)}] {topic}: {len(chunks)} chunks")
        else:
            print(f"  [{i+1}/{len(STARTER_TOPICS_EN)}] {topic}: FAILED")
        time.sleep(0.5)  # be nice to Wikipedia

    print(f"\nTotal evidence passages: {len(all_texts)}")

    # Embed and index
    print("Embedding evidence passages...")
    evidence_emb = embedder.embed(
        all_ids, all_texts, ["en"] * len(all_texts)
    )
    print("Building FAISS index...")
    retriever.build_index(all_ids, all_texts, evidence_emb.vectors)
    print(f"FAISS index built with {len(retriever)} passages")

    # ── Score each synthetic claim ──
    NLI_TOP_K = 3
    MIN_RELEVANCE = 0.3

    sem_sims = []
    nli_probs = []

    print(f"\nScoring {len(synth_df)} claims...")
    for idx, row in synth_df.iterrows():
        claim_text = row["claim_text"]
        language = row["language"]
        claim_id = row["claim_id"]

        # Embed claim
        emb_result = embedder.embed([claim_id], [claim_text], [language])
        query_vec = emb_result.vectors[0]

        # Retrieve evidence
        retrieval = retriever.retrieve(claim_id, query_vec, top_k=NLI_TOP_K)
        relevant = [p for p in retrieval.passages if p.score >= MIN_RELEVANCE]

        # SemSim
        if relevant:
            sem_sim = max(0.0, min(1.0, relevant[0].score))
        else:
            sem_sim = float("nan")

        # NLI
        if relevant:
            nli_results = nli_scorer.score_batch(
                claim_ids=[claim_id] * len(relevant),
                premises=[p.text for p in relevant],
                hypotheses=[claim_text] * len(relevant),
            )
            net_scores = [
                0.5 + 0.5 * (r.entailment_prob - r.contradiction_prob)
                for r in nli_results
            ]
            nli_prob = max(net_scores, key=lambda s: abs(s - 0.5))
        else:
            nli_prob = float("nan")

        sem_sims.append(sem_sim)
        nli_probs.append(nli_prob)

        if (idx + 1) % 20 == 0:
            print(f"  Scored {idx + 1}/{len(synth_df)} claims...")

    synth_df["sem_sim"] = sem_sims
    synth_df["nli_prob"] = nli_probs

    # Summary stats
    valid = synth_df[synth_df["sem_sim"].notna()]
    print(f"\nScoring complete. {len(valid)}/{len(synth_df)} claims got valid signals.")
    print(f"  sem_sim: mean={valid['sem_sim'].mean():.3f}, std={valid['sem_sim'].std():.3f}")
    print(f"  nli_prob: mean={valid['nli_prob'].mean():.3f}, std={valid['nli_prob'].std():.3f}")

    return synth_df


# ── Step 3: Merge + Split ───────────────────────────────────────────────

def merge_and_split(scored_synth: pd.DataFrame):
    """Merge synthetic hallucinations into gold dataset and create train/test splits."""
    print("\n" + "=" * 70)
    print("STEP 3: Merging into gold dataset v3 + train/test split")
    print("=" * 70)

    gold = pd.read_csv(GOLD_V2_CSV)
    # Drop old signal columns if present
    drop_cols = [c for c in gold.columns if c.endswith("_old")]
    gold = gold.drop(columns=drop_cols, errors="ignore")

    # Align columns
    keep_cols = [c for c in gold.columns if c in scored_synth.columns]
    for c in gold.columns:
        if c not in scored_synth.columns:
            scored_synth[c] = ""

    # Merge
    merged = pd.concat([gold, scored_synth[gold.columns]], ignore_index=True)

    # Save v3
    merged.to_csv(GOLD_V3_CSV, index=False)
    print(f"Saved {len(merged)} claims to {GOLD_V3_CSV}")

    # Class balance
    print("\nClass balance (v3):")
    print(merged["gold_verdict"].value_counts())
    print(f"\nBy language:")
    print(merged.groupby(["language", "gold_verdict"]).size().unstack(fill_value=0))

    # Stratified train/test split
    merged["strata"] = merged["language"] + "_" + merged["gold_verdict"]
    # Handle rare strata
    strata_counts = merged["strata"].value_counts()
    rare = strata_counts[strata_counts < 2].index
    rare_mask = merged["strata"].isin(rare)

    if rare_mask.any():
        train_rare = merged[rare_mask]
        splittable = merged[~rare_mask]
    else:
        train_rare = pd.DataFrame(columns=merged.columns)
        splittable = merged

    train_split, test_split = train_test_split(
        splittable, test_size=0.2, random_state=42,
        stratify=splittable["strata"]
    )
    train_df = pd.concat([train_split, train_rare], ignore_index=True)
    test_df = test_split

    # Drop strata column
    train_df = train_df.drop(columns=["strata"])
    test_df = test_df.drop(columns=["strata"])

    train_df.to_csv(TRAIN_CSV, index=False)
    test_df.to_csv(TEST_CSV, index=False)
    print(f"\nTrain: {len(train_df)} claims -> {TRAIN_CSV}")
    print(f"Test:  {len(test_df)} claims -> {TEST_CSV}")
    print(f"\nTrain class balance:")
    print(train_df["gold_verdict"].value_counts())
    print(f"\nTest class balance:")
    print(test_df["gold_verdict"].value_counts())


# ── Step 4: Train weights ──────────────────────────────────────────────

def train_weights():
    """Train CMHSA weights on balanced data."""
    print("\n" + "=" * 70)
    print("STEP 4: Training CMHSA weights")
    print("=" * 70)

    from member1_model.train_weights import train_language_weights

    results = {}
    for mode_name, semsim_flag in [("no_semsim", False), ("with_semsim", True)]:
        print(f"\n--- Mode: {mode_name} ---")
        mode_results = {}
        for lang in ["en", "hi"]:
            print(f"\n  Training {lang}...")
            alpha, beta, gamma = train_language_weights(
                TRAIN_CSV, lang, epochs=300, lr=0.05,
                semsim_votes=semsim_flag,
            )
            mode_results[lang] = {"alpha": alpha, "beta": beta, "gamma": gamma}

            # Save weights
            out_path = Path(f"weights_{lang}_{mode_name}.json")
            with open(out_path, "w") as f:
                json.dump({"language": lang, "alpha": alpha, "beta": beta,
                          "gamma": gamma, "semsim_votes": semsim_flag}, f, indent=2)
            print(f"  Saved to {out_path}")

        results[mode_name] = mode_results

    return results


# ── Step 5: Ablation ───────────────────────────────────────────────────

CLASSES = ["Hallucinated", "Uncertain", "Verified"]

ABLATION_CONFIGS = {
    "Full (S+N+KG)": {"semsim", "nli", "kg"},
    "SemSim only": {"semsim"},
    "NLI only": {"nli"},
    "SemSim + NLI": {"semsim", "nli"},
    "NLI + KG": {"nli", "kg"},
    "SemSim + KG": {"semsim", "kg"},
    "KG only": {"kg"},
}


def run_ablation(weight_results: dict):
    """Run ablation study on held-out test set."""
    print("\n" + "=" * 70)
    print("STEP 5: Ablation study on held-out test set")
    print("=" * 70)

    from member1_model.cmhsa import CMHSAScorer, ClaimSubScores

    test_df = pd.read_csv(TEST_CSV)
    for c in ["sem_sim", "nli_prob", "kg_conf"]:
        test_df[c] = pd.to_numeric(test_df[c], errors="coerce")

    RESULTS_DIR.mkdir(exist_ok=True)
    all_results = {}

    for mode_name, mode_weights in weight_results.items():
        print(f"\n{'='*50}")
        print(f"Mode: {mode_name}")
        print(f"{'='*50}")

        mode_results = {}

        for lang in ["en", "hi"]:
            w = mode_weights[lang]
            scorer = CMHSAScorer()
            scorer.load_weights(lang, w["alpha"], w["beta"], w["gamma"])

            lang_df = test_df[test_df["language"] == lang]
            if len(lang_df) == 0:
                continue

            print(f"\n  --- {lang} ({len(lang_df)} test claims) ---")
            print(f"  Weights: alpha={w['alpha']:.4f}  beta={w['beta']:.4f}  gamma={w['gamma']:.4f}")

            config_results = {}
            print(f"  {'Config':<16}{'Acc':>8}{'Macro-F1':>10}{'Hallu-F1':>10}{'Verif-F1':>10}")

            for config_name, allowed in ABLATION_CONFIGS.items():
                y_true, y_pred = [], []
                for _, row in lang_df.iterrows():
                    sub = ClaimSubScores(
                        claim_id=str(row["claim_id"]),
                        sem_sim=row["sem_sim"] if "semsim" in allowed and pd.notna(row["sem_sim"]) else None,
                        nli_prob=row["nli_prob"] if "nli" in allowed and pd.notna(row["nli_prob"]) else None,
                        kg_conf=row["kg_conf"] if "kg" in allowed and pd.notna(row["kg_conf"]) else None,
                    )
                    try:
                        sc = scorer.score_claim(sub, lang)
                        y_true.append(row["gold_verdict"])
                        y_pred.append(sc.verdict.value)
                    except ValueError:
                        pass  # no signals available

                if not y_true:
                    print(f"  {config_name:<16}{'--':>8}{'--':>10}{'--':>10}{'--':>10}  (no scoreable claims)")
                    continue

                acc = accuracy_score(y_true, y_pred)
                mf1 = f1_score(y_true, y_pred, labels=CLASSES, average="macro", zero_division=0)
                hf1 = f1_score(y_true, y_pred, labels=["Hallucinated"], average="macro", zero_division=0)
                vf1 = f1_score(y_true, y_pred, labels=["Verified"], average="macro", zero_division=0)
                print(f"  {config_name:<16}{acc:>8.3f}{mf1:>10.3f}{hf1:>10.3f}{vf1:>10.3f}")

                config_results[config_name] = {
                    "accuracy": round(acc, 4), "macro_f1": round(mf1, 4),
                    "hallu_f1": round(hf1, 4), "verif_f1": round(vf1, 4),
                    "n_scored": len(y_true),
                }

            # Majority baseline
            y_all = lang_df["gold_verdict"].tolist()
            maj_pred = ["Verified"] * len(y_all)
            maj_acc = accuracy_score(y_all, maj_pred)
            maj_mf1 = f1_score(y_all, maj_pred, labels=CLASSES, average="macro", zero_division=0)
            print(f"  {'Always-Verified':<16}{maj_acc:>8.3f}{maj_mf1:>10.3f}{'0.000':>10}{'--':>10}")

            config_results["always_verified_baseline"] = {
                "accuracy": round(maj_acc, 4), "macro_f1": round(maj_mf1, 4),
            }

            mode_results[lang] = config_results

        all_results[mode_name] = mode_results

    # Save results
    results_path = RESULTS_DIR / "ablation_results_v3.json"
    with open(results_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to {results_path}")

    return all_results


# ── Step 6: Summary ───────────────────────────────────────────────────

def print_summary(all_results: dict):
    """Print a thesis-ready summary of results."""
    print("\n" + "=" * 70)
    print("STEP 6: Results Summary")
    print("=" * 70)

    for mode_name, mode_results in all_results.items():
        print(f"\n### Weight Mode: {mode_name}")
        for lang, configs in mode_results.items():
            print(f"\n  Language: {lang}")
            print(f"  {'Config':<20}{'Acc':>8}{'Macro-F1':>10}{'Hallu-F1':>10}")
            print(f"  {'-'*48}")
            for config, metrics in configs.items():
                acc = metrics.get("accuracy", 0)
                mf1 = metrics.get("macro_f1", 0)
                hf1 = metrics.get("hallu_f1", "--")
                print(f"  {config:<20}{acc:>8.3f}{mf1:>10.3f}{str(hf1):>10}")

    # Key thesis questions
    print("\n" + "=" * 70)
    print("KEY THESIS QUESTIONS")
    print("=" * 70)

    for mode_name, mode_results in all_results.items():
        print(f"\n--- {mode_name} ---")
        for lang, configs in mode_results.items():
            full = configs.get("Full (S+N+KG)", {})
            sem_only = configs.get("SemSim only", {})
            nli_only = configs.get("NLI only", {})
            baseline = configs.get("always_verified_baseline", {})

            full_hf1 = full.get("hallu_f1", 0)
            sem_hf1 = sem_only.get("hallu_f1", 0)
            nli_hf1 = nli_only.get("hallu_f1", 0)
            full_mf1 = full.get("macro_f1", 0)
            base_mf1 = baseline.get("macro_f1", 0)

            print(f"\n  [{lang}] Does full fusion beat SemSim-only?")
            print(f"    Full macro-F1={full_mf1:.3f} vs SemSim-only macro-F1={sem_only.get('macro_f1', 0):.3f}")
            print(f"    -> {'YES' if full_mf1 > sem_only.get('macro_f1', 0) + 0.01 else 'NO / MARGINAL'}")

            print(f"  [{lang}] Does the model catch hallucinations?")
            print(f"    Hallu-F1: Full={full_hf1:.3f}, NLI-only={nli_hf1:.3f}, SemSim-only={sem_hf1:.3f}")
            print(f"    -> {'YES' if full_hf1 > 0.05 else 'NO'}")

            print(f"  [{lang}] Does the model beat always-Verified?")
            print(f"    Full macro-F1={full_mf1:.3f} vs baseline macro-F1={base_mf1:.3f}")
            print(f"    -> {'YES' if full_mf1 > base_mf1 else 'NO'}")


# ── Main ────────────────────────────────────────────────────────────────

def main():
    start_time = time.time()

    # Step 2: Score synthetic claims
    scored_synth = build_corpus_and_score(SYNTHETIC_CSV)

    # Step 3: Merge + split
    merge_and_split(scored_synth)

    # Step 4: Train weights
    weight_results = train_weights()

    # Step 5: Ablation
    ablation_results = run_ablation(weight_results)

    # Step 6: Summary
    print_summary(ablation_results)

    elapsed = time.time() - start_time
    print(f"\n{'='*70}")
    print(f"Total elapsed time: {elapsed/60:.1f} minutes")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
