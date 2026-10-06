"""Deploy Satya-Score to a Hugging Face Space, keeping the source code private.

Once, by you (deploy/DEPLOY.md): a Hugging Face account, and on this computer
    .venv/Scripts/python.exe -m huggingface_hub.cli.hf auth login      (a WRITE token)

Then:
    .venv/Scripts/python.exe deploy/push_to_hf.py --space satyascore --data   # first time
    .venv/Scripts/python.exe deploy/push_to_hf.py --space satyascore          # later updates

What it uploads
  <user>/satyascore-bundle  (PRIVATE dataset repository)
      code.tar.gz            committed code (git archive HEAD) + the built web app
      corpus_*_expanded.*    the 102,069-passage corpus (with --data, or when missing)
  <user>/<space>            (PUBLIC Space, Docker)
      Dockerfile (pinned to the bundle revisions above), README.md, fetch_bundle.py,
      requirements.txt, requirements-lock.txt
A Space upload starts a rebuild. The Space reads the bundle with its HF_TOKEN secret.
Only committed code is deployed: commit first, then run this.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from huggingface_hub import HfApi, get_token

ROOT = Path(__file__).resolve().parent.parent
SPACE_DIR = Path(__file__).resolve().parent / "space"
CODE_PATHS = ["member1_model", "member2_data", "member3_backend", "weights_en.json", "weights_hi.json",
              "calibration_en.json", "calibration_hi.json", "evidence_corpus_cache.json",
              "THIRD_PARTY_NOTICES.md"]
DATA_FILES = ["corpus_passages_expanded.json", "corpus_vectors_expanded.npy"]


def run(cmd: list[str], cwd: Path = ROOT, env: dict | None = None) -> bytes:
    return subprocess.run(cmd, cwd=cwd, env=env, check=True, capture_output=True).stdout


def space_url(space_id: str) -> str:
    """https://<user>-<space>.hf.space (Hugging Face lower-cases and replaces _ and . with -)."""
    return "https://" + re.sub(r"[^a-z0-9-]", "-", space_id.replace("/", "-").lower()) + ".hf.space"


def render_dockerfile(template: str, bundle: str, code_rev: str, data_rev: str) -> str:
    out = (template.replace("{{BUNDLE_REPO}}", bundle).replace("{{CODE_REV}}", code_rev)
           .replace("{{DATA_REV}}", data_rev))
    assert "{{" not in out, "unfilled placeholder in Dockerfile.template"
    return out


def build_web() -> Path:
    env = {**os.environ, "VITE_API_URL": "/api"}  # the web app calls the API on the same origin
    npm = "npm.cmd" if os.name == "nt" else "npm"
    run([npm, "run", "build"], cwd=ROOT / "web", env=env)
    dist = ROOT / "web" / "dist"
    if not (dist / "index.html").is_file():
        sys.exit("web build produced no web/dist/index.html")
    return dist


def code_archive(dist: Path) -> bytes:
    """git archive HEAD of CODE_PATHS + web/dist, as .tar.gz bytes."""
    committed = tarfile.open(fileobj=io.BytesIO(run(["git", "archive", "--format=tar", "HEAD", *CODE_PATHS])))
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as out:
        for member in committed.getmembers():
            out.addfile(member, committed.extractfile(member) if member.isfile() else None)
        out.add(dist, arcname="web/dist")
    return buf.getvalue()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--space", default="satyascore", help="Space name (created under your account)")
    ap.add_argument("--bundle", default="satyascore-bundle", help="private dataset repository name")
    ap.add_argument("--data", action="store_true", help="(re)upload the corpus files")
    args = ap.parse_args()

    if get_token() is None:
        sys.exit("Not logged in to Hugging Face. Run:  .venv/Scripts/python.exe -m huggingface_hub.cli.hf auth login")
    api = HfApi()
    user = api.whoami()["name"]
    space_id, bundle_id = f"{user}/{args.space}", f"{user}/{args.bundle}"

    dirty = run(["git", "status", "--porcelain", "--", *CODE_PATHS]).decode().strip()
    if dirty:
        sys.exit(f"Uncommitted changes in deployed files; commit them first:\n{dirty}")
    sha = run(["git", "rev-parse", "--short", "HEAD"]).decode().strip()

    # 1. private bundle: corpus (only when asked or missing) and code
    api.create_repo(bundle_id, repo_type="dataset", private=True, exist_ok=True)
    if not api.repo_info(bundle_id, repo_type="dataset").private:
        sys.exit(f"{bundle_id} exists and is PUBLIC; make it private on huggingface.co before deploying.")
    present = {f for f in api.list_repo_files(bundle_id, repo_type="dataset")}
    if args.data or not set(DATA_FILES) <= present:
        for name in DATA_FILES:
            print(f"uploading {name} ({(ROOT / name).stat().st_size / 1e6:.0f} MB) ...")
            api.upload_file(path_or_fileobj=str(ROOT / name), path_in_repo=name, repo_id=bundle_id,
                            repo_type="dataset", commit_message=f"corpus ({name})")
    print("building the web app ...")
    tar = code_archive(build_web())
    code_rev = api.upload_file(path_or_fileobj=tar, path_in_repo="code.tar.gz", repo_id=bundle_id,
                               repo_type="dataset", commit_message=f"code {sha}").oid
    info = api.get_paths_info(bundle_id, [DATA_FILES[1]], repo_type="dataset", expand=True)
    data_rev = info[0].last_commit.oid
    print(f"bundle {bundle_id}: code {code_rev[:10]} ({len(tar) / 1e6:.1f} MB), corpus {data_rev[:10]}")

    # 2. public Space (Docker). A new Space needs its secrets before the first build.
    try:
        api.repo_info(space_id, repo_type="space")
        new = False
    except Exception:
        api.create_repo(space_id, repo_type="space", space_sdk="docker", private=False)
        new = True
    if new:
        print(f"\nCreated the Space {space_id}. Before it can build, add two secrets at\n"
              f"  https://huggingface.co/spaces/{space_id}/settings  (Variables and secrets):\n"
              f"    HF_TOKEN              a READ token of your account (to read the private bundle)\n"
              f"    GOOGLE_FACTCHECK_KEY  your Google Fact Check Tools key (optional)\n"
              f"Then run this script again.")
        return

    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        # newline="\n": a Windows checkout may have CRLF line endings, which break the
        # backslash line continuations in a Dockerfile built on Linux.
        (stage / "Dockerfile").write_text(render_dockerfile(
            (SPACE_DIR / "Dockerfile.template").read_text(encoding="utf8"), bundle_id, code_rev, data_rev),
            encoding="utf8", newline="\n")
        for name in ["README.md", "fetch_bundle.py"]:
            shutil.copy(SPACE_DIR / name, stage / name)
        for name in ["requirements.txt", "requirements-lock.txt"]:
            shutil.copy(ROOT / name, stage / name)
        api.upload_folder(folder_path=str(stage), repo_id=space_id, repo_type="space",
                          commit_message=f"Deploy {sha}")
    print(f"\nUploaded. The Space is rebuilding (the first build takes about 15-25 minutes):\n"
          f"  build logs: https://huggingface.co/spaces/{space_id}?logs=build\n"
          f"  the app:    {space_url(space_id)}")


if __name__ == "__main__":
    main()
