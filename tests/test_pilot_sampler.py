import pandas as pd
import pytest
from dataset_pipeline.pilot_sampler import sample_pilot


def _make_fake_pool(n_per_stratum=51):
    """5 domains x 2 languages, n_per_stratum claims each -> ~510 total."""
    domains = ["healthcare", "history", "science", "government", "sports"]
    languages = ["en", "hi"]
    rows = []
    claim_id = 0
    for d in domains:
        for lang in languages:
            for _ in range(n_per_stratum):
                rows.append({
                    "claim_id": claim_id,
                    "claim_text": f"claim {claim_id}",
                    "language": lang,
                    "domain": d,
                })
                claim_id += 1
    return pd.DataFrame(rows)


def test_pilot_size_matches_target():
    df = _make_fake_pool()
    pilot_df, remaining_df = sample_pilot(df, pilot_size=60)
    assert len(pilot_df) == 60
    assert len(remaining_df) == len(df) - 60


def test_no_overlap_between_pilot_and_remaining():
    df = _make_fake_pool()
    pilot_df, remaining_df = sample_pilot(df, pilot_size=60)
    assert set(pilot_df["claim_id"]).isdisjoint(set(remaining_df["claim_id"]))


def test_every_stratum_represented():
    df = _make_fake_pool()
    pilot_df, _ = sample_pilot(df, pilot_size=60, min_per_stratum=3)
    counts = pilot_df.groupby(["domain", "language"]).size()
    assert (counts >= 3).all()
    assert len(counts) == 10  # 5 domains x 2 languages


def test_missing_column_raises():
    df = pd.DataFrame({"claim_id": [1, 2], "claim_text": ["a", "b"]})
    with pytest.raises(ValueError):
        sample_pilot(df)


def test_reproducible_with_fixed_seed():
    df = _make_fake_pool()
    pilot1, _ = sample_pilot(df, random_state=42)
    pilot2, _ = sample_pilot(df, random_state=42)
    assert set(pilot1["claim_id"]) == set(pilot2["claim_id"])


def test_handles_uneven_real_world_strata():
    """Mirrors the real dataset's uneven strata (e.g. history/hi has far
    fewer claims than healthcare/en) — makes sure allocation doesn't
    request more than a small stratum actually has."""
    rows = []
    claim_id = 0
    sizes = {
        ("government", "en"): 86, ("government", "hi"): 46,
        ("healthcare", "en"): 99, ("healthcare", "hi"): 37,
        ("history", "en"): 35, ("history", "hi"): 26,
        ("science", "en"): 56, ("science", "hi"): 37,
        ("sports", "en"): 43, ("sports", "hi"): 44,
    }
    for (domain, lang), n in sizes.items():
        for _ in range(n):
            rows.append({
                "claim_id": claim_id, "claim_text": f"c{claim_id}",
                "domain": domain, "language": lang,
            })
            claim_id += 1
    df = pd.DataFrame(rows)
    pilot_df, remaining_df = sample_pilot(df, pilot_size=60)
    assert len(pilot_df) <= 60
    assert set(pilot_df["claim_id"]).isdisjoint(set(remaining_df["claim_id"]))
    counts = pilot_df.groupby(["domain", "language"]).size()
    assert (counts >= 3).all()
