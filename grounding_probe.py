"""Design probe (not a decision test): current NLI vs MiniCheck on the SAME retrieved passages."""
import random, sys
sys.path.insert(0, r"C:\Users\vivek\Downloads\satyascore")
import numpy as np, pandas as pd, torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import member3_backend.api as api
from aggregation_eval import sample_texts
from member3_backend.pipeline import MIN_RELEVANCE_THRESHOLD

api.load_starter_corpus(); api._warmup_models()
pipe = api._pipeline
S = r"C:\Users\vivek\AppData\Local\Temp\claude\C--Users-vivek-Downloads-satyascore\c180dfbf-bc10-4f41-acdc-e952d67f4ab7\scratchpad"

COMMON = [("Humans can breathe naturally underwater.", 0), ("Human can breath naturally underwater.", 0),
    ("Humans can breathe underwater without any equipment.", 0), ("Fish breathe using gills.", 1),
    ("The Sun revolves around the Earth.", 0), ("The Earth revolves around the Sun.", 1),
    ("Water boils at 100 degrees Celsius at sea level.", 1), ("Humans have three lungs.", 0),
    ("Humans have two lungs.", 1), ("Penguins can fly long distances.", 0), ("Snakes have legs.", 0),
    ("Bats are mammals.", 1), ("Spiders are insects.", 0), ("The Moon produces its own light.", 0),
    ("Plants make food by photosynthesis.", 1)]
miss = pd.read_csv(S + r"\miss_analysis.csv")
genuine_idx = [0, 1, 2, 3, 4, 35, 37, 38, 39, 40, 41, 42, 43, 44]  # #1-5, 36, 38-45 of the analysis
groups = {"common sense": COMMON,
          "genuine hallucinations (train)": [(miss.claim[i], 0, miss.lang[i]) for i in genuine_idx]}
tr = pd.read_csv(r"C:\Users\vivek\Downloads\satyascore\gold_train_clean.csv")
ver = tr[tr.gold_verdict == "Verified"].sample(40, random_state=19)
groups["true chatbot claims (train, 40)"] = [(r.claim_text, 1, r.language) for r in ver.itertuples()]
fresh = []
for it in sample_texts(19):
    for c in pipe.claim_extractor.extract(it["text"], it["lang"]):
        fresh.append((c.text, 1, it["lang"]))
groups["fresh true Wikipedia sentences (40)"] = random.Random(19).sample(fresh, 40)

tok = AutoTokenizer.from_pretrained("lytang/MiniCheck-DeBERTa-v3-Large")
mc = AutoModelForSequenceClassification.from_pretrained("lytang/MiniCheck-DeBERTa-v3-Large").to("cuda").eval()

def minicheck(docs, claim):
    if not docs: return []
    enc = tok(docs, [claim] * len(docs), truncation=True, max_length=512, padding=True, return_tensors="pt").to("cuda")
    with torch.no_grad():
        return torch.softmax(mc(**enc).logits, -1)[:, 1].tolist()

rows = []
for g, items in groups.items():
    items = [(x[0], x[1], x[2] if len(x) > 2 else "en") for x in items]
    pipe.expander.expand([(c, l) for c, _, l in items])
    for claim, true, lang in items:
        v = api._embedder.embed(["q"], [claim], [lang]).vectors[0]
        ps = [p for p in api._retriever.retrieve("q", v, top_k=pipe.nli_top_k).passages if p.score >= MIN_RELEVANCE_THRESHOLD]
        nli = api._nli_scorer.score_batch(["q"] * len(ps), [p.text for p in ps], [claim] * len(ps)) if ps else []
        m = minicheck([p.text for p in ps], claim)
        best = int(np.argmax(m)) if m else None
        rows.append({"group": g, "claim": claim, "lang": lang, "true": true,
                     "nli_max_e": max((r.entailment_prob for r in nli), default=0.0),
                     "mc_max": max(m, default=0.0),
                     "mc_best_title": ps[best].passage_id.split("::")[0] if best is not None else ""})
    print("done", g, flush=True)
d = pd.DataFrame(rows); d.to_csv(S + r"\grounding_probe.csv", index=False, encoding="utf-8")
for g, x in d.groupby("group", sort=False):
    for t in (1, 0):
        y = x[x.true == t]
        if len(y):
            print(f"{g:38} {'TRUE ' if t else 'FALSE'} n={len(y):2}  NLI supports (e>=0.5): {int((y.nli_max_e >= 0.5).sum()):2}   "
                  f"MiniCheck supports (p>=0.5): {int((y.mc_max >= 0.5).sum()):2}")
