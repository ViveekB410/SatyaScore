"""Deploy Satya-Score to Azure Container Apps (works with an Azure for Students subscription).

Once, by you (deploy/azure/AZURE.md): Azure for Students, Azure CLI, Docker Desktop, `az login`.
Then, from the project folder:

    .venv/Scripts/python.exe deploy/azure/azure_deploy.py setup     # once: region, resource group, registry, environment
    .venv/Scripts/python.exe deploy/azure/azure_deploy.py build     # build the image here, push it to the registry
    .venv/Scripts/python.exe deploy/azure/azure_deploy.py deploy    # create or update the app; prints the link
    .venv/Scripts/python.exe deploy/azure/azure_deploy.py wake      # keep 1 copy running (demo days; ~$1.5/day)
    .venv/Scripts/python.exe deploy/azure/azure_deploy.py sleep     # back to scale-to-zero (~$5/month in total)
    .venv/Scripts/python.exe deploy/azure/azure_deploy.py status    # link, running copies, image

Why build here: Azure does not run cloud image builds (ACR Tasks) on student/credit subscriptions.
The registry is private and the app pulls from it with a managed identity: no passwords anywhere.
Only committed code is deployed (git archive HEAD); commit first.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HERE = Path(__file__).resolve().parent
STATE = ROOT / "instance" / "azure_deploy.json"   # names chosen by `setup` (git-ignored folder)
CODE_PATHS = ["member1_model", "member2_data", "member3_backend", "weights_en.json", "weights_hi.json",
              "calibration_en.json", "calibration_hi.json", "evidence_corpus_cache.json", "THIRD_PARTY_NOTICES.md"]
DATA_FILES = ["corpus_passages_expanded.json", "corpus_vectors_expanded.npy"]
RG, ENV, APP = "satyascore-rg", "satyascore-env", "satyascore"
CPU, MEMORY, PORT = "2", "4Gi", 7860       # measured peak 2.9 GB on CPU
# Preferred regions (nearest first). A student subscription allows only some regions; `setup`
# reads the allowed list from the subscription's policy and takes the first one here that is allowed.
PREFERRED = ["centralindia", "southindia", "westindia", "southeastasia", "eastasia", "uaenorth",
             "japaneast", "koreacentral", "australiaeast", "northeurope", "westeurope", "francecentral",
             "uksouth", "swedencentral", "eastus", "eastus2", "westus2", "centralus", "canadacentral"]


# --- helpers -----------------------------------------------------------------------

def az(*args: str, parse: bool = True, check: bool = True):
    """Run an Azure CLI command; returns parsed JSON (or text). Errors stop the script."""
    exe = shutil.which("az") or shutil.which("az.cmd")
    if not exe:
        sys.exit("Azure CLI not found. Install it:  winget install -e --id Microsoft.AzureCLI  (then open a new terminal)")
    r = subprocess.run([exe, *args] + (["-o", "json"] if parse else []), capture_output=True, text=True,
                       encoding="utf8", errors="replace")
    if r.returncode != 0:
        if not check:
            return None
        sys.exit(f"az {' '.join(args[:3])} ... failed:\n{r.stderr.strip()[-1500:]}")
    if not parse:
        return r.stdout.strip()
    return json.loads(r.stdout) if r.stdout.strip() else None


def run(cmd: list[str], cwd: Path = ROOT, env: dict | None = None, capture: bool = True) -> bytes:
    return subprocess.run(cmd, cwd=cwd, env=env, check=True, capture_output=capture).stdout


def allowed_regions(assignments: list[dict]) -> set[str] | None:
    """Regions allowed by an 'allowed locations' policy on the subscription; None if no such policy."""
    found: set[str] = set()
    for a in assignments or []:
        for p in (a.get("parameters") or {}).values():
            v = p.get("value") if isinstance(p, dict) else None
            if isinstance(v, list) and v and all(isinstance(x, str) for x in v) and \
                    any(x.lower().replace(" ", "") in PREFERRED for x in v):
                found |= {x.lower().replace(" ", "") for x in v}
    return found or None


def pick_region(allowed: set[str] | None, supported: set[str]) -> str | None:
    """First preferred region that the subscription allows and Container Apps supports."""
    for r in PREFERRED:
        if r in supported and (allowed is None or r in allowed):
            return r
    return None


def image_ref(registry: str, tag: str) -> str:
    return f"{registry}.azurecr.io/satyascore:{tag}"


def load_state() -> dict:
    if not STATE.is_file():
        sys.exit("Run `setup` first.")
    return json.loads(STATE.read_text(encoding="utf8"))


def logged_in() -> dict:
    acct = az("account", "show", check=False)
    if not acct:
        sys.exit("Not logged in to Azure. Run:  az login")
    return acct


# --- commands ------------------------------------------------------------------------

def cmd_setup(_):
    acct = logged_in()
    print(f"subscription: {acct['name']} ({acct['state']})")
    for ns in ("Microsoft.App", "Microsoft.ContainerRegistry", "Microsoft.OperationalInsights"):
        az("provider", "register", "--namespace", ns, "--wait", parse=False)
    allowed = allowed_regions(az("policy", "assignment", "list", "--disable-scope-strict-match", check=False) or [])
    types = az("provider", "show", "-n", "Microsoft.App", "--query",
               "resourceTypes[?resourceType=='managedEnvironments'].locations | [0]")
    supported = {x.lower().replace(" ", "") for x in types or []}
    region = pick_region(allowed, supported)
    if not region:
        sys.exit(f"No usable region. Allowed by your subscription: {sorted(allowed or [])}")
    print(f"region: {region}" + (f"  (your subscription allows: {', '.join(sorted(allowed))})" if allowed else ""))
    az("group", "create", "-n", RG, "-l", region)
    state = json.loads(STATE.read_text(encoding="utf8")) if STATE.is_file() else {}
    registry = state.get("registry") or f"satyascore{secrets.token_hex(4)}"
    if not az("acr", "show", "-n", registry, "-g", RG, check=False):
        print(f"creating registry {registry} (Basic, private) ...")
        az("acr", "create", "-n", registry, "-g", RG, "--sku", "Basic", "-l", region)
    if not az("containerapp", "env", "show", "-n", ENV, "-g", RG, check=False):
        print("creating the Container Apps environment (a few minutes) ...")
        az("containerapp", "env", "create", "-n", ENV, "-g", RG, "-l", region, "--logs-destination", "none")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"region": region, "registry": registry}, indent=1), encoding="utf8")
    print("setup done. Next:  build")


def stage_context(dist: Path, dest: Path) -> None:
    """Build context: committed code + web build under app/, corpus and requirements at the top."""
    app = dest / "app"
    app.mkdir(parents=True)
    tar = tarfile.open(fileobj=io.BytesIO(run(["git", "archive", "--format=tar", "HEAD", *CODE_PATHS])))
    tar.extractall(app, filter="data")
    shutil.copytree(dist, app / "web" / "dist")
    for name in DATA_FILES + ["requirements.txt", "requirements-lock.txt"]:
        shutil.copy2(ROOT / name, dest / name)
    # LF line endings: a Windows checkout may turn them into CRLF, which breaks the backslash
    # line continuations when the Dockerfile is read on Linux.
    (dest / "Dockerfile").write_text((HERE / "Dockerfile").read_text(encoding="utf8"), encoding="utf8", newline="\n")


def cmd_build(_):
    state = load_state()
    logged_in()
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        sys.exit("Docker is not running. Start Docker Desktop and wait until it says 'Engine running'.")
    dirty = run(["git", "status", "--porcelain", "--", *CODE_PATHS, "requirements.txt", "requirements-lock.txt"]).decode().strip()
    if dirty:
        sys.exit(f"Uncommitted changes in deployed files; commit them first:\n{dirty}")
    sha = run(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
    print("building the web app ...")
    npm = "npm.cmd" if os.name == "nt" else "npm"
    run([npm, "run", "build"], cwd=ROOT / "web", env={**os.environ, "VITE_API_URL": "/api"})
    tag, latest = image_ref(state["registry"], sha), image_ref(state["registry"], "latest")
    with tempfile.TemporaryDirectory() as tmp:
        stage_context(ROOT / "web" / "dist", Path(tmp))
        print(f"docker build {tag} (first time: 15-30 min; later builds reuse the cached layers) ...")
        run(["docker", "build", "-t", tag, "-t", latest, tmp], capture=False)
    az("acr", "login", "-n", state["registry"], parse=False)
    print("pushing (first time ~4.5 GB; later only the changed layers) ...")
    run(["docker", "push", tag], capture=False)
    run(["docker", "push", latest], capture=False)
    STATE.write_text(json.dumps({**state, "image": tag}, indent=1), encoding="utf8")
    print(f"pushed {tag}. Next:  deploy")


def cmd_deploy(_):
    state = load_state()
    logged_in()
    image = state.get("image") or sys.exit("Run `build` first.")
    if az("containerapp", "show", "-n", APP, "-g", RG, check=False):
        print(f"updating the app to {image} ...")
        az("containerapp", "update", "-n", APP, "-g", RG, "--image", image)
    else:
        print("creating the app (pulls the image from the private registry with a managed identity) ...")
        az("containerapp", "create", "-n", APP, "-g", RG, "--environment", ENV, "--image", image,
           "--registry-server", f"{state['registry']}.azurecr.io", "--registry-identity", "system",
           "--ingress", "external", "--target-port", str(PORT), "--cpu", CPU, "--memory", MEMORY,
           "--min-replicas", "0", "--max-replicas", "1")
        set_startup_probe()
    fqdn = az("containerapp", "show", "-n", APP, "-g", RG, "--query", "properties.configuration.ingress.fqdn")
    print(f"\nThe app: https://{fqdn}\n(first start after a deploy or a sleep: about 2-4 minutes while the "
          f"models load; then fast)")


def set_startup_probe():
    """Loading the models on 2 CPUs can take a few minutes; give the startup probe up to ~5.5 min
    (30 s + 10 x 30 s) so the container is not restarted while it is still loading."""
    import yaml
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "app.yaml"
        f.write_text(az("containerapp", "show", "-n", APP, "-g", RG, "-o", "yaml", parse=False), encoding="utf8")
        spec = yaml.safe_load(f.read_text(encoding="utf8"))
        container = spec["properties"]["template"]["containers"][0]
        container["probes"] = [{"type": "Startup", "tcpSocket": {"port": PORT}, "initialDelaySeconds": 30,
                                "periodSeconds": 30, "failureThreshold": 10, "timeoutSeconds": 5}]
        f.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf8")
        az("containerapp", "update", "-n", APP, "-g", RG, "--yaml", str(f))


def cmd_scale(minimum: int):
    def run_(_):
        load_state()
        logged_in()
        az("containerapp", "update", "-n", APP, "-g", RG, "--min-replicas", str(minimum))
        print("awake: 1 copy kept running (about $1.5/day). Run `sleep` after the demo." if minimum else
              "sleeping: scales to zero when idle (first visit after idle waits 2-4 minutes).")
    return run_


def cmd_status(_):
    state = load_state()
    logged_in()
    app = az("containerapp", "show", "-n", APP, "-g", RG, check=False)
    if not app:
        print(f"region {state['region']}, registry {state['registry']}: no app yet (run build, then deploy)")
        return
    props = app["properties"]
    replicas = az("containerapp", "replica", "list", "-n", APP, "-g", RG, check=False) or []
    print(f"link:     https://{props['configuration']['ingress']['fqdn']}\n"
          f"image:    {props['template']['containers'][0]['image']}\n"
          f"running:  {len(replicas)} copy/copies (min {props['template']['scale'].get('minReplicas', 0)})\n"
          f"region:   {state['region']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in [("setup", cmd_setup), ("build", cmd_build), ("deploy", cmd_deploy),
                     ("wake", cmd_scale(1)), ("sleep", cmd_scale(0)), ("status", cmd_status)]:
        sub.add_parser(name).set_defaults(fn=fn)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
