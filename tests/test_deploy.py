"""Tests for deploy/push_to_hf.py helpers and the Space Dockerfile template (no network)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("push_to_hf", ROOT / "deploy" / "push_to_hf.py")
push = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(push)


def test_space_url():
    assert push.space_url("ViveekB410/satyascore") == "https://viveekb410-satyascore.hf.space"
    assert push.space_url("a_b/c.d") == "https://a-b-c-d.hf.space"


def test_dockerfile_template_is_filled_and_pinned():
    out = push.render_dockerfile((ROOT / "deploy" / "space" / "Dockerfile.template").read_text(encoding="utf8"),
                                 "user/satyascore-bundle", "c0de" * 10, "da7a" * 10)
    assert "{{" not in out
    assert "python fetch_bundle.py user/satyascore-bundle " + "da7a" * 10 + " corpus_passages_expanded.json" in out
    assert "python fetch_bundle.py user/satyascore-bundle " + "c0de" * 10 + " code.tar.gz" in out
    assert "--mount=type=secret,id=HF_TOKEN" in out
    assert "download.pytorch.org/whl/cpu" in out          # CPU torch on the Space
    assert "-c requirements-lock.txt" in out              # tested versions
    assert "member3_backend.serve:create_app" in out and '"--factory"' in out
    assert "SATYASCORE_COOKIE_SECURE=true" in out


def test_dockerfile_keeps_lf_even_from_a_crlf_template():
    out = push.render_dockerfile("RUN a && \\\r\n    b\r\n{{BUNDLE_REPO}} {{CODE_REV}} {{DATA_REV}}\r\n", "r", "c", "d")
    # render keeps the text; the CRLF -> LF conversion happens on read_text/write_text(newline="\n")
    assert "{{" not in out
    src = push.Path(push.__file__).read_text(encoding="utf8")
    assert 'newline="\\n"' in src


def test_deployed_paths_exist_and_are_committed_files():
    for p in push.CODE_PATHS:
        assert (ROOT / p).exists(), p
    for p in push.DATA_FILES:
        assert p.startswith("corpus_") and p.endswith(("_expanded.json", "_expanded.npy"))
