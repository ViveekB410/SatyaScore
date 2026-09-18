from unittest.mock import MagicMock, patch

import pytest

from member2_data.wikidata_connector import WikidataConnector


def _mock_response(json_data, status_ok=True):
    resp = MagicMock()
    resp.json.return_value = json_data
    if not status_ok:
        resp.raise_for_status.side_effect = Exception("HTTP error")
    return resp


def test_verify_triple_found():
    session = MagicMock()
    session.get.return_value = _mock_response({"boolean": True})

    wd = WikidataConnector(session=session)
    result = wd.verify_triple("Q1058", "P39", "Q14212", language="en")

    assert result.found is True
    assert result.confidence == 1.0
    assert result.used_fallback_label is False
    assert result.source == "live"


def test_verify_triple_not_found():
    session = MagicMock()
    session.get.return_value = _mock_response({"boolean": False})

    wd = WikidataConnector(session=session)
    result = wd.verify_triple("Q1058", "P39", "Q99999", language="en")

    assert result.found is False
    assert result.confidence == 0.0


def test_result_is_cached_on_second_call():
    session = MagicMock()
    session.get.return_value = _mock_response({"boolean": True})

    wd = WikidataConnector(session=session)
    first = wd.verify_triple("Q1058", "P39", "Q14212", language="en")
    second = wd.verify_triple("Q1058", "P39", "Q14212", language="en")

    assert first.source == "live"
    assert second.source == "cache"
    # Only one real HTTP call should have been made — the second was served from cache.
    assert session.get.call_count == 1


def test_get_label_falls_back_to_english_when_hindi_missing():
    session = MagicMock()

    def side_effect(url, params, headers, timeout):
        query = params["query"]
        if 'LANG(?label) = "hi"' in query:
            return _mock_response({"results": {"bindings": []}})  # no Hindi label
        return _mock_response({"results": {"bindings": [{"label": {"value": "Mount Everest"}}]}})

    session.get.side_effect = side_effect

    wd = WikidataConnector(session=session)
    label, used_fallback = wd.get_label("Q513", language="hi")

    assert label == "Mount Everest"
    assert used_fallback is True


def test_get_label_no_fallback_needed_when_native_label_exists():
    session = MagicMock()
    session.get.return_value = _mock_response(
        {"results": {"bindings": [{"label": {"value": "एवरेस्ट पर्वत"}}]}}
    )

    wd = WikidataConnector(session=session)
    label, used_fallback = wd.get_label("Q513", language="hi")

    assert label == "एवरेस्ट पर्वत"
    assert used_fallback is False


def test_network_failure_returns_not_found_rather_than_raising():
    import requests

    session = MagicMock()
    session.get.side_effect = requests.exceptions.ConnectionError("network down")

    wd = WikidataConnector(session=session)
    result = wd.verify_triple("Q1058", "P39", "Q14212", language="en")

    assert result.found is False
    assert result.confidence == 0.0
