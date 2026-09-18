"""
Combines finished annotator CSVs into an IAA report + adjudicated dataset.

WHERE THIS GOES: dataset_pipeline/combine_annotations.py

WHAT IT EXPECTS: each annotator submits back their copy of
pilot_annotation_BLIND.csv with the `gold_verdict` column filled in
(exactly "Verified", "Uncertain", or "Hallucinated" — case-sensitive,
matches member2_data.annotation_schema.Verdict's enum values).

Run:
    python -m dataset_pipeline.combine_annotations \
        --annotator alice=alice_annotated.csv \
        --annotator bob=bob_annotated.csv \
        --annotator carol=carol_annotated.csv \
        --original dataset_pipeline/output/pilot_annotation.csv \
        --output-dir dataset_pipeline/output

Produces:
    iaa_report.txt          — pairwise kappa, mean kappa, go/no-go recommendation
    adjudicated_pilot.csv   — original columns + gold_verdict + adjudication_method,
                              only for claims that were unanimous or clear-majority
    needs_adjudication.csv  — claims that tied and need a human group decision
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from member2_data.annotation_schema import Adjudicator, Annotation, Verdict
from member2_data.iaa import build_iaa_report


def load_annotator_csv(path: str, annotator_id: str) -> list[Annotation]:
    annotations = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw_verdict = row.get("gold_verdict", "").strip()
            if not raw_verdict:
                continue  # skip rows this annotator left blank
            try:
                verdict = Verdict(raw_verdict)
            except ValueError:
                raise ValueError(
                    f"{path}, claim_id={row.get('claim_id')}: invalid gold_verdict "
                    f"{raw_verdict!r} — must be exactly 'Verified', 'Uncertain', "
                    f"or 'Hallucinated' (case-sensitive)."
                )
            annotations.append(
                Annotation(claim_id=row["claim_id"], annotator_id=annotator_id, verdict=verdict)
            )
    return annotations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--annotator", action="append", required=True,
        help="name=path/to/their_annotated.csv — repeat for each annotator",
    )
    parser.add_argument("--original", required=True, help="Path to the original pilot_annotation.csv")
    parser.add_argument("--output-dir", default=".", help="Where to write output files")
    args = parser.parse_args()

    # -- Load all annotators' work --
    annotations_by_claim: dict[str, list[Annotation]] = {}
    for entry in args.annotator:
        name, path = entry.split("=", 1)
        for ann in load_annotator_csv(path, name):
            annotations_by_claim.setdefault(ann.claim_id, []).append(ann)

    # -- IAA report --
    report = build_iaa_report(annotations_by_claim)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / "iaa_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"Mean pairwise Cohen's Kappa: {report.mean_kappa:.3f}\n")
        f.write(f"Meets minimum target (0.65): {report.meets_minimum_target}\n")
        f.write(f"Meets stretch target (0.75): {report.meets_stretch_target}\n\n")
        f.write("Pairwise breakdown:\n")
        for p in report.pairwise:
            f.write(
                f"  {p.annotator_a} vs {p.annotator_b}: kappa={p.kappa:.3f} "
                f"(n={p.n_shared_claims}, meets_target={p.meets_minimum_target})\n"
            )
        f.write(f"\nRecommendation:\n{report.recommendation}\n")

    print(f"IAA report written -> {report_path}")
    print(f"Mean kappa: {report.mean_kappa:.3f} "
          f"({'PASS' if report.meets_minimum_target else 'BELOW TARGET — see recommendation'})")

    # -- Adjudicate every claim (unanimous / majority / needs-human) --
    adjudicator = Adjudicator()
    resolved = adjudicator.resolve_batch(annotations_by_claim)

    # -- Merge gold_verdict back onto the original claim data --
    with open(args.original, newline="", encoding="utf-8") as f:
        original_rows = {row["claim_id"]: row for row in csv.DictReader(f)}
        fieldnames = list(next(iter(original_rows.values())).keys())

    resolved_out, needs_adjudication_out = [], []
    for label in resolved:
        base_row = dict(original_rows.get(label.claim_id, {"claim_id": label.claim_id}))
        base_row["gold_verdict"] = label.gold_verdict.value
        base_row["adjudication_method"] = label.method
        if label.needs_manual_adjudication:
            needs_adjudication_out.append(base_row)
        else:
            resolved_out.append(base_row)

    out_fieldnames = fieldnames + ["adjudication_method"] if "adjudication_method" not in fieldnames else fieldnames

    resolved_path = output_dir / "adjudicated_pilot.csv"
    with open(resolved_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fieldnames)
        writer.writeheader()
        writer.writerows(resolved_out)

    needs_adj_path = output_dir / "needs_adjudication.csv"
    with open(needs_adj_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fieldnames)
        writer.writeheader()
        writer.writerows(needs_adjudication_out)

    print(f"\n{len(resolved_out)} claims auto-resolved -> {resolved_path}")
    print(f"{len(needs_adjudication_out)} claims need group discussion -> {needs_adj_path}")


if __name__ == "__main__":
    main()
