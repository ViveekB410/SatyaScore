"""Tests for deploy/azure/azure_deploy.py helpers and the Azure Dockerfile (no Azure, no Docker)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("azure_deploy", ROOT / "deploy" / "azure" / "azure_deploy.py")
azd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(azd)


def test_allowed_regions_from_a_student_policy():
    assignments = [
        {"displayName": "Allowed resource deployment regions",
         "parameters": {"listOfAllowedLocations": {"value": ["eastasia", "southeastasia", "uaenorth",
                                                                 "koreacentral", "japaneast"]}}},
        {"displayName": "something else", "parameters": {"effect": {"value": "Audit"}}},
    ]
    assert azd.allowed_regions(assignments) == {"eastasia", "southeastasia", "uaenorth", "koreacentral", "japaneast"}
    assert azd.allowed_regions([]) is None


def test_pick_region_prefers_india_then_nearest_allowed():
    supported = {"centralindia", "southeastasia", "eastasia", "westeurope"}
    assert azd.pick_region(None, supported) == "centralindia"                         # no policy
    assert azd.pick_region({"southeastasia", "eastasia"}, supported) == "southeastasia"
    assert azd.pick_region({"brazilsouth"}, supported) is None


def test_image_ref():
    assert azd.image_ref("satyascoreab12cd34", "1a2b3c4") == "satyascoreab12cd34.azurecr.io/satyascore:1a2b3c4"


def test_build_context_layout(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html></html>", encoding="utf8")
    if not all((ROOT / f).is_file() for f in azd.DATA_FILES):
        import pytest
        pytest.skip("expanded corpus not built on this machine")
    ctx = tmp_path / "ctx"
    azd.stage_context(dist, ctx)
    assert (ctx / "Dockerfile").is_file() and (ctx / "requirements-lock.txt").is_file()
    assert all((ctx / f).is_file() for f in azd.DATA_FILES)
    assert (ctx / "app" / "member3_backend" / "serve.py").is_file()
    assert (ctx / "app" / "web" / "dist" / "index.html").is_file()
    assert not (ctx / "app" / "instance").exists()          # never ship accounts or caches
    assert not (ctx / "app" / "tests").exists()


def test_dockerfile_matches_the_staged_layout_and_settings():
    d = (ROOT / "deploy" / "azure" / "Dockerfile").read_text(encoding="utf8")
    assert "COPY corpus_passages_expanded.json corpus_vectors_expanded.npy ./" in d
    assert "COPY app/ ./" in d
    assert "download.pytorch.org/whl/cpu" in d and "-c requirements-lock.txt" in d
    assert 'SATYASCORE_API_KEYS=""' in d and "SATYASCORE_COOKIE_SECURE=true" in d
    assert '"--port", "7860"' in d and azd.PORT == 7860
