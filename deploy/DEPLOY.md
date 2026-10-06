# Deploying Satya-Score to Hugging Face Spaces

> **Status (2026-10-07):** Hugging Face now requires a **PRO subscription** for Docker Spaces on
> its free CPU hardware (the Hub answers `402 Payment Required` when the Space is created). The
> private bundle (`<user>/satyascore-bundle`) uploads fine; the Space itself needs PRO. Without
> PRO, use the **public link** from the laptop (`deploy/start_public.py`, PROJECT_GUIDE §3.2b),
> or **Azure for Students** (free $100 credit): see **`deploy/azure/AZURE.md`**.

The app (website + API) runs in one Docker container on a free Hugging Face Space:
2 CPU cores, 16 GB RAM, public address `https://<user>-satyascore.hf.space`.
The source code stays private: the Space contains only a Dockerfile, a README, a small
download script and the requirements files. Code, the built website and the
102,069-passage corpus are in a **private** dataset repository that the Space reads while
it builds, using a token you store as a Space secret.

```
your computer ──push_to_hf.py──► <user>/satyascore-bundle   (private: code, web build, corpus)
              └────────────────► <user>/satyascore          (public Space: Dockerfile, README)
                                       │ build reads the bundle with the HF_TOKEN secret
browser ──► https://<user>-satyascore.hf.space  (website at /, API at /api)
```

## One-time setup (you, about 15 minutes)

1. **Create a Hugging Face account** at https://huggingface.co/join and confirm your email.
2. **Create two access tokens** at https://huggingface.co/settings/tokens:
   - a **Write** token, for uploading from this computer;
   - a **Read** token, for the Space to read the private bundle.
   Keep them to yourself; do not paste them into chat or into any file in the project.
3. **Log in on this computer** (paste the *Write* token when asked):
   ```
   .venv/Scripts/python.exe -m huggingface_hub.cli.hf auth login
   ```
4. **First run** creates the Space and the private bundle, uploads the corpus (~385 MB) and
   then stops so you can add the secrets:
   ```
   .venv/Scripts/python.exe deploy/push_to_hf.py --space satyascore --data
   ```
5. **Add the secrets** in the Space: Settings → Variables and secrets → *New secret*:
   | Name | Value |
   |---|---|
   | `HF_TOKEN` | the **Read** token from step 2 |
   | `GOOGLE_FACTCHECK_KEY` | your Google Fact Check Tools key (optional; without it, published fact-checks are skipped) |
6. **Second run** uploads the Dockerfile and starts the build (first build: about 15-25 minutes):
   ```
   .venv/Scripts/python.exe deploy/push_to_hf.py --space satyascore
   ```
   Follow the build in the Space's *Logs* tab. When it shows `Application startup complete`,
   open `https://<user>-satyascore.hf.space`.

## Updating the deployed app

Commit your changes, then run step 6 again. Only committed code is deployed (the script
refuses to run with uncommitted changes in deployed files). Add `--data` only when the corpus
files change.

## What to know

- **Open the app at its own address** (`https://<user>-satyascore.hf.space`), not inside the
  Hugging Face page: browsers block the login cookie inside the embedded frame.
- **Speed:** the Space has no GPU; a typical answer takes several seconds longer than on the
  laptop. Use the laptop (the demo steps in PROJECT_GUIDE.md) for the live demo and viva.
- **Sleeping:** a free Space sleeps after 48 hours without visitors; the next visit wakes it
  (1-2 minutes). Open it a few minutes before showing it to anyone.
- **Accounts and history are not permanent** on the free Space: they are kept until the
  Space restarts or rebuilds (persistent storage is a paid option).
- **Password reset codes** are created with the administrator command
  (`python -m member3_backend.auth reset-code <email>`), which needs a shell in the container;
  free Spaces do not offer one, so on the Space a forgotten password means a new account.
- **Licences:** WHO data is for non-commercial use; the Space README lists the sources.
- **Changing tokens:** delete or regenerate them at https://huggingface.co/settings/tokens at
  any time; update the `HF_TOKEN` secret if you replace the Read token.
