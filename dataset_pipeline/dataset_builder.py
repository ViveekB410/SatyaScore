"""
Builds the annotation-ready dataset from collected LLM responses.

PRD ref: Section 11.2:
    Step 3 — Claim Decomposition: use the Claim Extractor to decompose
             responses into atomic claims.
    Step 4 — Expert Annotation: annotators label each claim (this module
             produces the CSV they annotate; it does NOT do the labeling
             itself — that's a human step, via Label Studio or similar
             per Section 10.1).
    Step 7 — Dataset Release: CSV format here is designed to convert
             directly into member1_model/train_weights.py's expected
             input once the `gold_verdict` column is filled in.

This module pre-fills sem_sim/nli_prob/kg_conf for each claim using the
real pipeline (Member 1+2+3's work) BEFORE annotation, not as a
replacement for human judgement — the PRD's own gold labels come from
human annotators (Step 4), not from the model scoring itself. Pre-filling
these columns just gives annotators useful context and saves needing a
second pass to compute them after labels exist.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from dataset_pipeline.response_collector import LLMResponse
from member3_backend.pipeline import DetectionPipeline

CSV_COLUMNS = [
    "claim_id",
    "source_query_id",
    "source_llm",
    "language",
    "domain",
    "claim_text",
    "sem_sim",
    "nli_prob",
    "kg_conf",
    "gold_verdict",  # blank until annotated — Verified / Uncertain / Hallucinated
    "evidence_url",  # blank until annotated
]


@dataclass
class UnannotatedClaimRow:
    claim_id: str
    source_query_id: str
    source_llm: str
    language: str
    domain: str
    claim_text: str
    sem_sim: float | None
    nli_prob: float | None
    kg_conf: float | None


class DatasetBuilder:
    def __init__(self, pipeline: DetectionPipeline):
        self.pipeline = pipeline

    def build_rows_from_response(
        self, response: LLMResponse, language: str, domain: str
    ) -> list[UnannotatedClaimRow]:
        """Decomposes one LLM response into atomic claims and pre-fills
        each claim's SemSim/NLI/KG sub-scores using the real pipeline."""
        try:
            result = self.pipeline.run(response.response_text, language)
        except ValueError:
            return []  # no claims extractable from this response — skip it

        rows = []
        for i, (claim_text, sub_score) in enumerate(zip(result.claims, result.sub_scores)):
            rows.append(
                UnannotatedClaimRow(
                    claim_id=f"{response.query_id}_{response.source_llm}_{i}",
                    source_query_id=response.query_id,
                    source_llm=response.source_llm,
                    language=language,
                    domain=domain,
                    claim_text=claim_text,
                    sem_sim=sub_score.sem_sim,
                    nli_prob=sub_score.nli_prob,
                    kg_conf=sub_score.kg_conf,
                )
            )
        return rows

    def build_dataset(
        self, responses: list[LLMResponse], language_by_query_id: dict[str, str], domain_by_query_id: dict[str, str]
    ) -> list[UnannotatedClaimRow]:
        all_rows = []
        for response in responses:
            language = language_by_query_id.get(response.query_id, "en")
            domain = domain_by_query_id.get(response.query_id, "unknown")
            all_rows.extend(self.build_rows_from_response(response, language, domain))
        return all_rows

    @staticmethod
    def export_csv(rows: list[UnannotatedClaimRow], output_path: str | Path) -> None:
        """Writes the annotation-ready CSV — annotators fill in
        `gold_verdict` and `evidence_url` per Section 11.2 Step 4."""
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "claim_id": row.claim_id,
                        "source_query_id": row.source_query_id,
                        "source_llm": row.source_llm,
                        "language": row.language,
                        "domain": row.domain,
                        "claim_text": row.claim_text,
                        "sem_sim": "" if row.sem_sim is None else round(row.sem_sim, 4),
                        "nli_prob": "" if row.nli_prob is None else round(row.nli_prob, 4),
                        "kg_conf": "" if row.kg_conf is None else round(row.kg_conf, 4),
                        "gold_verdict": "",
                        "evidence_url": "",
                    }
                )

    @staticmethod
    def to_training_csv(annotated_csv_path: str | Path, training_csv_path: str | Path) -> int:
        """
        Converts an ANNOTATED dataset CSV (gold_verdict filled in by
        humans) into the exact column format member1_model/train_weights.py
        expects: claim_id, language, sem_sim, nli_prob, kg_conf, gold_verdict.

        Rows without a gold_verdict, or with NO signal at all, are skipped.
        A row with a gold_verdict and at least one present signal is KEPT even
        if some signals are blank — kg_conf is blank on almost every real row
        (Wikidata / relation coverage is sparse), and requiring all three
        present is what previously emptied the entire training file. Blanks are
        preserved as-is; train_weights.py masks absent signals per row and
        renormalises the remaining weights (mirroring CMHSAScorer.score_claim).
        Returns the number of rows written.
        """
        written = 0
        with open(annotated_csv_path, newline="", encoding="utf-8") as infile, open(
            training_csv_path, "w", newline="", encoding="utf-8"
        ) as outfile:
            reader = csv.DictReader(infile)
            writer = csv.DictWriter(
                outfile, fieldnames=["claim_id", "language", "sem_sim", "nli_prob", "kg_conf", "gold_verdict"]
            )
            writer.writeheader()
            for row in reader:
                if not row.get("gold_verdict"):
                    continue
                # Keep the row if it has AT LEAST ONE present signal. Absent
                # signals stay blank and are masked out per-row during training
                # — requiring all three present is what previously emptied the
                # entire training file whenever kg_conf was unpopulated (which,
                # in practice, is almost always).
                if not any(row.get(c) for c in ("sem_sim", "nli_prob", "kg_conf")):
                    continue
                writer.writerow(
                    {
                        "claim_id": row["claim_id"],
                        "language": row["language"],
                        "sem_sim": row.get("sem_sim", ""),
                        "nli_prob": row.get("nli_prob", ""),
                        "kg_conf": row.get("kg_conf", ""),
                        "gold_verdict": row["gold_verdict"],
                    }
                )
                written += 1
        return written
