# Deploying Satya-Score to Azure (Azure for Students)

A permanent https address (`https://satyascore.<random>.<region>.azurecontainerapps.io`) on
**Azure Container Apps**, paid from the free Azure for Students credit ($100, no credit card).
The image is built on this laptop and stored in a **private** Azure Container Registry; the app
pulls it with a managed identity, so no password or token is copied anywhere.

## Cost (Central India prices, checked 2026-10-07 from the Azure price API)

| Item | Price | In practice |
|---|---|---|
| Container Registry, Basic | $0.167/day | **~$5/month** (always) |
| App while running, 2 vCPU + 4 GiB | $0.000024/vCPU-s + $0.000003/GiB-s | first ~25 running hours/month free (180,000 vCPU-s, 360,000 GiB-s); then ~$0.22/hour |
| App kept awake but idle (`wake`) | $0.000003/vCPU-s + $0.000003/GiB-s | ~$1.5/day |

Default mode is **sleep** (scale to zero): about **$5/month**, so the credit lasts the year. The
first visit after ~5 idle minutes waits 2-4 minutes while the container starts and loads the models.
On demo days run `wake` (instant responses), and `sleep` afterwards.
Memory was measured on CPU: 2.3 GB after loading, 2.9 GB peak, so 4 GiB is enough.

## One-time setup (you)

1. **Azure for Students:** https://azure.microsoft.com/free/students — sign up with your college
   email (no credit card). Wait until the portal shows the *Azure for Students* subscription.
2. **Azure CLI:** `winget install -e --id Microsoft.AzureCLI`
3. **Docker Desktop:** `winget install -e --id Docker.DockerDesktop` — restart if asked, start
   Docker Desktop, accept its terms (free for personal and education use) and wait for
   *Engine running*. It needs WSL 2; Docker Desktop offers to install it.
4. Open a **new** terminal in the project folder and log in (a browser window opens):
   ```
   az login
   ```

## Deploy (the script does the rest)

```
.venv\Scripts\python.exe deploy\azure\azure_deploy.py setup    # once, a few minutes
.venv\Scripts\python.exe deploy\azure\azure_deploy.py build    # first time 15-30 min build + ~4.5 GB upload
.venv\Scripts\python.exe deploy\azure\azure_deploy.py deploy   # prints the link
```

- `setup` reads which regions your student subscription allows (usually about five, often not
  India) and picks the nearest allowed one; creates the resource group `satyascore-rg`, a private
  registry and the Container Apps environment (logging off, to avoid log charges).
- `build` deploys **committed** code only (commit first); builds the web app and the image here
  and pushes it. Later builds push only the changed code layer (a few MB).
- `deploy` creates the app (2 vCPU, 4 GiB, 0-1 copies, port 7860) or updates its image.

**Google fact-checks (optional):** the key stays out of the scripts. To enable fact-checks on
Azure, run these yourself, replacing `<your-key>` (do not paste the key into chat):
```
az containerapp secret set -n satyascore -g satyascore-rg --secrets factcheck-key=<your-key>
az containerapp update -n satyascore -g satyascore-rg --set-env-vars GOOGLE_FACTCHECK_KEY=secretref:factcheck-key
```

## Day to day

```
.venv\Scripts\python.exe deploy\azure\azure_deploy.py status   # link, copies running, image
.venv\Scripts\python.exe deploy\azure\azure_deploy.py wake     # before a demo
.venv\Scripts\python.exe deploy\azure\azure_deploy.py sleep    # after it
```
Update after code changes: commit, then `build` and `deploy`.
Check the remaining credit: https://www.microsoftazuresponsorships.com/balance

## What to know

- **Accounts and history are not permanent yet:** they are lost when the app scales to zero or is
  updated. Keeping them needs an Azure Files share mounted at `/app/instance` (a few cents a month);
  not set up yet.
- **Speed:** CPU only. On the laptop's CPU (10 threads) a new 6-claim answer took 13.7 s and a
  repeat 0.7 s; with 2 cloud vCPUs expect new answers to take longer (estimate 30-50 s, not yet
  measured on Azure). Use the laptop (or `wake`) for the viva demo.
- **Password reset codes** need a shell in the container: `az containerapp exec -n satyascore -g satyascore-rg --command bash`,
  then `python -m member3_backend.auth reset-code <email>`.
- **Remove everything** (stops all charges): `az group delete -n satyascore-rg` (asks to confirm).
- **Not yet verified:** the Docker build itself (Docker is not installed on the laptop yet) and the
  first start on Azure. If either fails, the error is printed; send it for a fix.
