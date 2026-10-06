---
title: Satya-Score
emoji: ✅
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: Claim-level fact checking of AI answers in English and Hindi
---

# Satya-Score: An AI Hallucination Detection & Scoring Framework

Paste an answer written by an AI chatbot, in English or Hindi. Satya-Score splits it into
factual claims and checks each one against professional fact-checks, World Bank and WHO
statistics, the Wikidata knowledge graph and Wikipedia, and marks it Verified, Uncertain or
Hallucinated with the source that decided it.

**Open the app at its own address** (the "Embed this Space" link, `https://<user>-<space>.hf.space`)
rather than inside the Hugging Face page: logging in uses a cookie that browsers block inside
an embedded frame.

B.Tech project, Department of Artificial Intelligence & Data Science,
Prof. Ram Meghe Institute of Technology & Research, Badnera-Amravati, 2026-27.

Notes: the free Space runs on CPU (a check takes several seconds) and sleeps after 48 hours
without visitors (the first visit then takes 1-2 minutes). Accounts and history are kept
until the Space restarts. Sources: Wikipedia (CC BY-SA 4.0), Wikidata (CC0), World Bank
(CC BY 4.0), WHO GHO (CC BY-NC-SA 3.0 IGO, non-commercial use), Google Fact Check Tools.
