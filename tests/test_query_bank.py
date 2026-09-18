import pytest

from dataset_pipeline.query_bank import get_seed_queries, expand_queries


def test_seed_queries_cover_all_five_domains_both_languages():
    queries = get_seed_queries()
    domains = {q.domain for q in queries}
    languages = {q.language for q in queries}
    assert domains == {"healthcare", "history", "science", "government", "sports"}
    assert languages == {"en", "hi"}


def test_seed_queries_count():
    queries = get_seed_queries()
    # 5 domains x 10 questions x 2 languages
    assert len(queries) == 100


def test_seed_query_ids_are_unique():
    queries = get_seed_queries()
    ids = [q.query_id for q in queries]
    assert len(ids) == len(set(ids))


def test_expand_queries_fills_template_per_entity():
    expanded = expand_queries("sports", ["Virat Kohli", "Sachin Tendulkar"], language="en")
    assert len(expanded) == 4  # 2 templates x 2 entities for "sports"
    texts = [q.text for q in expanded]
    assert any("Virat Kohli" in t for t in texts)
    assert any("Sachin Tendulkar" in t for t in texts)


def test_expand_queries_rejects_non_english():
    with pytest.raises(NotImplementedError):
        expand_queries("sports", ["Virat Kohli"], language="hi")


def test_expand_queries_rejects_domain_without_templates():
    with pytest.raises(ValueError):
        expand_queries("healthcare", ["Aspirin"], language="en")
