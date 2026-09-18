"""
NOTE ON SCOPE: These tests cover auth, input validation, and rate limiting
— the parts of the API that don't require a loaded embedding model or a
built FAISS index. A full /detect success-path test needs (a) XLM-R
weights downloaded and (b) a real evidence corpus indexed, neither of
which belong in a fast unit test suite. That's better covered by an
integration/smoke test run manually or in CI with model caching.
"""

import pytest
from fastapi.testclient import TestClient

from member3_backend.api import RATE_LIMIT_PER_MINUTE, _request_log, app

client = TestClient(app)
VALID_KEY = "dev-key-satyascore-2026"


@pytest.fixture(autouse=True)
def _reset_rate_limit_state():
    """Rate-limit tracking is in-memory and module-level — reset it between
    tests so one test's requests don't leak into another's count."""
    _request_log.clear()
    yield
    _request_log.clear()


def test_health_endpoint_no_auth_required():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_detect_without_api_key_rejected():
    response = client.post("/detect", json={"text": "The sky is blue.", "language": "en"})
    # Missing required header -> FastAPI returns 422, not 401, since the
    # header itself is absent rather than present-but-invalid.
    assert response.status_code == 422


def test_detect_with_invalid_api_key_rejected():
    response = client.post(
        "/detect",
        json={"text": "The sky is blue.", "language": "en"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401


def test_detect_with_missing_text_field_rejected():
    response = client.post(
        "/detect", json={"language": "en"}, headers={"X-API-Key": VALID_KEY}
    )
    assert response.status_code == 422


def test_detect_with_invalid_language_rejected():
    response = client.post(
        "/detect",
        json={"text": "Some text.", "language": "fr"},  # not in en/hi/mr
        headers={"X-API-Key": VALID_KEY},
    )
    assert response.status_code == 422


def test_detect_with_empty_text_rejected():
    response = client.post(
        "/detect", json={"text": "", "language": "en"}, headers={"X-API-Key": VALID_KEY}
    )
    assert response.status_code == 422


def test_detect_without_faiss_index_returns_503():
    # The module-level _retriever in api.py has no index built by default
    # in this test run, so a syntactically valid request should still fail
    # gracefully with 503 rather than crashing.
    response = client.post(
        "/detect",
        json={"text": "The sky is blue.", "language": "en"},
        headers={"X-API-Key": VALID_KEY},
    )
    assert response.status_code == 503


def test_rate_limit_blocks_after_threshold():
    # Drive the in-memory rate limiter over its threshold directly rather
    # than firing 100+ real HTTP requests through TestClient (slow, and
    # would still hit the 503 above before rate limiting even matters).
    from member3_backend.api import require_api_key

    for _ in range(RATE_LIMIT_PER_MINUTE):
        require_api_key(VALID_KEY)  # should not raise

    with pytest.raises(Exception) as exc_info:
        require_api_key(VALID_KEY)
    assert "429" in str(exc_info.value) or "Rate limit" in str(exc_info.value)
