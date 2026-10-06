"""Space build step: download files from the private bundle repository.

    python fetch_bundle.py <bundle_repo> <revision> <file> [<file> ...]

The token is the HF_TOKEN Space secret, mounted at /run/secrets/HF_TOKEN for this build
step only (it is not stored in the image). .tar.gz files are unpacked into /app; other
files are placed in /app as they are.
"""
import shutil
import sys
import tarfile
from pathlib import Path

from huggingface_hub import hf_hub_download

APP = Path("/app")


def main(repo: str, revision: str, files: list[str]) -> None:
    token = Path("/run/secrets/HF_TOKEN").read_text().strip()
    for name in files:
        path = hf_hub_download(repo, name, repo_type="dataset", revision=revision, token=token,
                               local_dir="/tmp/bundle")
        if name.endswith(".tar.gz"):
            with tarfile.open(path) as tar:
                tar.extractall(APP, filter="data")
        else:
            shutil.move(path, APP / name)
        print(f"fetched {name} @ {revision[:10]}")
    shutil.rmtree("/tmp/bundle", ignore_errors=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
