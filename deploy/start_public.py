"""Run Satya-Score on this laptop and share it through a public https link (Cloudflare tunnel).

    .venv/Scripts/python.exe deploy/start_public.py            # build the web app, start, print the link
    .venv/Scripts/python.exe deploy/start_public.py --no-build # reuse the last web build

Needs cloudflared (winget install --id Cloudflare.cloudflared -e). Uses Cloudflare's free
"quick tunnel": no Cloudflare account, a new random https://<words>.trycloudflare.com link
each start, and the link works only while this script runs. Stop with Ctrl+C.

The app (website at /, API at /api, member3_backend/serve.py) listens on 127.0.0.1 only;
the tunnel is the one way in from outside. Accounts and history are the laptop's usual
database (instance/satyascore.db), and the GPU is used, so checks are as fast as in the demo.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 7860
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def build_web() -> None:
    npm = "npm.cmd" if os.name == "nt" else "npm"
    print("building the web app ...", flush=True)
    subprocess.run([npm, "run", "build"], cwd=ROOT / "web", check=True, capture_output=True,
                   env={**os.environ, "VITE_API_URL": "/api"})


def start_tunnel(cloudflared: str) -> tuple[subprocess.Popen, str]:
    """Start a quick tunnel to the local port and return (process, public URL)."""
    proc = subprocess.Popen([cloudflared, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{PORT}"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf8",
                            errors="replace")
    found: list[str] = []

    def read():
        for line in proc.stdout:  # keep draining so cloudflared never blocks on a full pipe
            if not found and (m := URL_RE.search(line)):
                found.append(m.group(0))

    threading.Thread(target=read, daemon=True).start()
    for _ in range(120):
        if found:
            return proc, found[0]
        if proc.poll() is not None:
            sys.exit("cloudflared stopped before giving a link (is the internet connection up?)")
        time.sleep(0.5)
    proc.terminate()
    sys.exit("cloudflared gave no link within 60 s")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-build", action="store_true", help="reuse web/dist from the last build")
    args = ap.parse_args()

    cloudflared = shutil.which("cloudflared") or next(
        (str(p) for p in [Path(os.environ.get("ProgramFiles(x86)", "")) / "cloudflared" / "cloudflared.exe",
                          Path(os.environ.get("ProgramFiles", "")) / "cloudflared" / "cloudflared.exe",
                          Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "cloudflared.exe"]
         if p.is_file()), None)
    if not cloudflared:
        sys.exit("cloudflared is not installed. Run:  winget install --id Cloudflare.cloudflared -e  "
                 "(then open a new terminal)")
    if not args.no_build or not (ROOT / "web" / "dist" / "index.html").is_file():
        build_web()

    tunnel, url = start_tunnel(cloudflared)
    # The tunnel is https, so the session cookie can be Secure (browsers also accept Secure
    # cookies on http://localhost). Only cloudflared, on this machine, may set X-Forwarded-For.
    os.environ["SATYASCORE_CORS_ORIGINS"] = f"{url},http://127.0.0.1:{PORT},http://localhost:{PORT}"
    os.environ["SATYASCORE_COOKIE_SECURE"] = "true"
    # No X-API-Key access from outside: the development key is written in the repository.
    # Visitors use the website (guests: 20 checks/minute; signed-in users: 100).
    os.environ["SATYASCORE_API_KEYS"] = ""
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    print("\n" + "=" * 64 + f"\n  Public link:  {url}\n  On this laptop: http://localhost:{PORT}\n"
          "  The models take about a minute to load; the link works after\n"
          "  'Application startup complete'. Stop with Ctrl+C.\n" + "=" * 64 + "\n", flush=True)
    try:
        import uvicorn
        sys.path.insert(0, str(ROOT))
        uvicorn.run("member3_backend.serve:create_app", factory=True, host="127.0.0.1", port=PORT,
                    proxy_headers=True, forwarded_allow_ips="127.0.0.1")
    finally:
        tunnel.terminate()


if __name__ == "__main__":
    main()
