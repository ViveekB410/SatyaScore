"""
v2data/build_eval_sets.py -- builds the Version 2 evaluation sets defined in results/v2_data_PROTOCOL.md.
No label is written by hand: every label comes from a public human-labelled dataset or is true by
construction. Output: v2data/sets/<set>_<dev|test>.csv with columns
    item_id, set, split, language, text, label (true/false), meta

Sets: mushroom (claim labels mapped from human span labels), fever, xfact_hi (false only),
hiwiki (true Hindi Wikipedia sentences + number-altered copies), v1gold.

    .venv/Scripts/python.exe v2data/build_eval_sets.py            (all sets; needs internet for xfact/hiwiki)
    .venv/Scripts/python.exe v2data/build_eval_sets.py hiwiki     (one set)
"""
from __future__ import annotations

import io
import json
import random
import re
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from member2_data._http import USER_AGENT, polite_get  # noqa: E402

DATA = ROOT / "benchmarks" / "data"
OUT = ROOT / "v2data" / "sets"
SEED = 20261012
COLS = ["item_id", "set", "split", "language", "text", "label", "meta"]


LABEL_NAMES = {"true": "Verified", "false": "Hallucinated"}  # not "true"/"false": pandas would read booleans


def save(rows: list[dict], name: str) -> None:
    df = pd.DataFrame(rows, columns=COLS)
    df["label"] = df["label"].map(lambda v: LABEL_NAMES.get(v, v))
    for split in ("dev", "test"):
        part = df[df.split == split]
        part.to_csv(OUT / f"{name}_{split}.csv", index=False, encoding="utf-8")
        print(f"  {name}_{split}: {len(part)} items | {part.groupby(['language', 'label']).size().to_dict()}")


# ---------------------------------------------------------------- 1. Mu-SHROOM claim labels
MIN_OVERLAP = 3  # characters (protocol)


def build_mushroom() -> None:
    from member3_backend.claim_extractor import ClaimExtractor
    ex = ClaimExtractor()
    rows, dropped = [], 0
    for lang in ("hi", "en"):
        for split, fname in (("dev", "validation"), ("test", "test")):
            d = pd.read_parquet(DATA / f"mushroom_{lang}_{fname}.parquet")
            for r in d.itertuples(index=False):
                gold = set()
                for a, b in r.hard_labels:
                    gold.update(range(int(a), int(b)))
                try:
                    claims = ex.extract(r.model_output_text, lang)
                except ValueError:
                    claims = []
                for n, c in enumerate(claims):
                    ov = len(gold & set(range(c.start_char, c.end_char)))
                    if 0 < ov < MIN_OVERLAP:
                        dropped += 1
                        continue
                    rows.append({"item_id": f"{r.id}_c{n:02d}", "set": "mushroom", "split": split, "language": lang,
                                 "text": c.text, "label": "false" if ov >= MIN_OVERLAP else "true",
                                 "meta": json.dumps({"answer_id": r.id, "start": c.start_char, "end": c.end_char,
                                                     "overlap_chars": ov, "model": r.model_id}, ensure_ascii=False)})
    print(f"mushroom: dropped {dropped} ambiguous claims (1-{MIN_OVERLAP - 1} overlapping characters)")
    save(rows, "mushroom")


# ---------------------------------------------------------------- 2. FEVER
def build_fever() -> None:
    rows_all = [json.loads(l) for l in open(DATA / "fever_paper_dev.jsonl", encoding="utf-8")]
    test_rng = random.Random(20261010)  # the v1 test sample, exactly as public_benchmark_eval.fever_sample
    test_ids = set()
    pools = {lab: sorted((r for r in rows_all if r["label"] == lab), key=lambda r: r["id"]) for lab in ("SUPPORTS", "REFUTES")}
    for lab in ("SUPPORTS", "REFUTES"):
        test_ids |= {r["id"] for r in test_rng.sample(pools[lab], 150)}
    dev_rng = random.Random(20261013)
    rows = []
    for lab in ("SUPPORTS", "REFUTES"):
        test_part = [r for r in pools[lab] if r["id"] in test_ids]
        dev_part = dev_rng.sample([r for r in pools[lab] if r["id"] not in test_ids], 150)
        for split, part in (("test", test_part), ("dev", dev_part)):
            rows += [{"item_id": f"fever-{r['id']}", "set": "fever", "split": split, "language": "en", "text": r["claim"],
                      "label": "true" if lab == "SUPPORTS" else "false", "meta": ""} for r in part]
    save(rows, "fever")


# ---------------------------------------------------------------- 3. X-FACT Hindi
def build_xfact() -> None:
    rows = []
    for split, fname in (("dev", "dev"), ("test", "test")):
        path = DATA / f"xfact_hi_{fname}.csv"
        if not path.exists():
            r = requests.get(f"https://huggingface.co/datasets/utahnlp/x-fact/resolve/main/hi/{fname}-00000-of-00001.csv",
                             timeout=120, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            path.write_bytes(r.content)
        d = pd.read_csv(path)
        for i, r in enumerate(d.itertuples(index=False)):
            rows.append({"item_id": f"xfact-hi-{fname}-{i:03d}", "set": "xfact_hi", "split": split, "language": "hi",
                         "text": str(r.claim).strip(), "label": "false",
                         "meta": json.dumps({"xfact_label": r.label, "site": r.site}, ensure_ascii=False)})
    save(rows, "xfact_hi")


# ---------------------------------------------------------------- 4. Hindi Wikipedia, constructed
HI_API = "https://hi.wikipedia.org/w/api.php"
DEV2ASC = str.maketrans("०१२३४५६७८९", "0123456789")
ASC2DEV = str.maketrans("0123456789", "०१२३४५६७८९")
NUM = re.compile(r"(?<![\w.-])([\d०-९]{1,3}(?:,[\d०-९]{2,3})+|[\d०-९]+(?:\.[\d०-९]+)?)(?![\w-])")  # whole numbers only, not inside a word or code
TARGET_ARTICLES = 150


def indexed_hindi_titles() -> set[str]:
    from member3_backend.wiki_expander import indexed_titles_from_cache, indexed_titles_from_passages
    titles = indexed_titles_from_cache(ROOT / "evidence_corpus_cache.json")
    for name in ("corpus_passages_expanded.json", "corpus_passages_demo.json"):
        p = ROOT / name
        if p.exists():
            titles |= indexed_titles_from_passages(json.loads(p.read_text(encoding="utf-8")))
    return {t for lang, t in titles if lang == "hi"}


BRACKETS = re.compile(r"\s*[(\[][^()\[\]]*[)\]]")
MONTHS = ("जनवरी", "फ़रवरी", "फरवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "सितम्बर",
          "अक्टूबर", "अक्तूबर", "नवंबर", "नवम्बर", "दिसंबर", "दिसम्बर")
LAST_YEAR = 2026


def first_numeric_sentence(extract: str) -> str | None:
    """The FIRST sentence of the lead (it names the subject), bracketed asides removed (the extractor
    removes them too), if it is 6-40 words long and still contains a number."""
    parts = re.split(r"(?<=[।!?])\s+", " ".join(extract.split()), maxsplit=1)
    s = " ".join(BRACKETS.sub("", parts[0]).split()) if parts and parts[0] else ""
    if 6 <= len(s.split()) <= 40 and NUM.search(s) and s.endswith(("।", "!", "?")):
        return s
    return None


def _is_day_of_month(sentence: str, m: re.Match) -> bool:
    after, before = sentence[m.end(1):m.end(1) + 12].strip(), sentence[max(0, m.start(1) - 12):m.start(1)].strip()
    return after.startswith(MONTHS) or before.endswith(MONTHS) and len(m.group(1)) <= 2


def alter_number(sentence: str, rng: random.Random) -> str | None:
    """Change one number by the protocol rule, keeping its script (Devanagari / ASCII): a year
    (1000-2026) if there is one, moved by 3-30 years and kept at or before 2026; otherwise the first
    number that is not a day of the month, scaled by a factor in [1.5, 3] or [0.3, 0.7]."""
    matches = [m for m in NUM.finditer(sentence) if not _is_day_of_month(sentence, m)]
    years = [m for m in matches if re.fullmatch(r"\d{4}", m.group(1).translate(DEV2ASC))
             and 1000 <= int(m.group(1).translate(DEV2ASC)) <= LAST_YEAR]
    m = years[0] if years else (matches[0] if matches else None)
    if not m:
        return None
    raw = m.group(1)
    devanagari = any(ch in "०१२३४५६७८९" for ch in raw)
    value_txt = raw.translate(DEV2ASC).replace(",", "")
    try:
        value = float(value_txt)
    except ValueError:
        return None
    if "." not in value_txt and 1000 <= value <= LAST_YEAR:     # a year, kept in the past
        shift = rng.randint(3, 30)
        new = int(value) + shift if rng.random() < 0.5 and int(value) + shift <= LAST_YEAR else int(value) - shift
        new_txt = str(new)
    else:
        factor = rng.uniform(1.5, 3.0) if rng.random() < 0.5 else rng.uniform(0.3, 0.7)
        new_val = value * factor
        if "." in value_txt:
            new_txt = f"{new_val:.{len(value_txt.split('.')[1])}f}"
        else:
            new_int = max(1, round(new_val))
            if new_int == int(value):
                new_int += 2
            new_txt = f"{new_int:,}" if "," in raw else str(new_int)
    if devanagari:
        new_txt = new_txt.translate(ASC2DEV)
    if new_txt == raw:
        return None
    return sentence[:m.start(1)] + new_txt + sentence[m.end(1):]


def build_hiwiki() -> None:
    rng = random.Random(SEED)
    session = requests.Session()
    skip = indexed_hindi_titles()
    print(f"hiwiki: {len(skip)} indexed Hindi titles excluded")
    articles, seen = [], set()
    for _ in range(200):  # at most 200 batches of random titles
        if len(articles) >= TARGET_ARTICLES:
            break
        r = polite_get(session, HI_API, {"action": "query", "format": "json", "list": "random", "rnnamespace": 0,
                                         "rnlimit": 20}, timeout=30).json()
        titles = [x["title"] for x in r["query"]["random"] if x["title"] not in skip and x["title"] not in seen]
        seen |= set(titles)
        if not titles:
            continue
        e = polite_get(session, HI_API, {"action": "query", "format": "json", "prop": "extracts", "exintro": 1,
                                         "explaintext": 1, "redirects": 1, "titles": "|".join(titles)}, timeout=30).json()
        for page in e.get("query", {}).get("pages", {}).values():
            s = first_numeric_sentence(page.get("extract") or "")
            if s and len(articles) < TARGET_ARTICLES:
                articles.append((page["title"], s))
    rows = []
    order = list(range(len(articles)))
    rng.shuffle(order)
    dev_set = set(order[: len(order) // 2])
    for i, (title, sentence) in enumerate(articles):
        altered = alter_number(sentence, rng)
        if altered is None:
            continue
        split = "dev" if i in dev_set else "test"
        meta = json.dumps({"article": title}, ensure_ascii=False)
        rows.append({"item_id": f"hiwiki-{i:03d}-t", "set": "hiwiki", "split": split, "language": "hi",
                     "text": sentence, "label": "true", "meta": meta})
        rows.append({"item_id": f"hiwiki-{i:03d}-f", "set": "hiwiki", "split": split, "language": "hi",
                     "text": altered, "label": "false", "meta": meta})
    print(f"hiwiki: {len(articles)} articles sampled")
    save(rows, "hiwiki")


# ---------------------------------------------------------------- 4b. Hindi place-name swaps
# Hindi names of Indian states / union territories and of frequently mentioned countries. A true sentence
# naming one of them gets a false copy naming another one from the same list.
HI_STATES = ["आंध्र प्रदेश", "अरुणाचल प्रदेश", "असम", "बिहार", "छत्तीसगढ़", "गोवा", "गुजरात", "हरियाणा",
             "हिमाचल प्रदेश", "झारखंड", "झारखण्ड", "कर्नाटक", "केरल", "मध्य प्रदेश", "महाराष्ट्र", "मणिपुर",
             "मेघालय", "मिज़ोरम", "मिजोरम", "नागालैंड", "ओडिशा", "पंजाब", "राजस्थान", "सिक्किम", "तमिलनाडु",
             "तमिल नाडु", "तेलंगाना", "त्रिपुरा", "उत्तर प्रदेश", "उत्तराखण्ड", "उत्तराखंड", "पश्चिम बंगाल", "दिल्ली",
             "जम्मू और कश्मीर", "लद्दाख", "पुदुचेरी", "चण्डीगढ़", "चंडीगढ़"]
HI_COUNTRIES = ["भारत", "पाकिस्तान", "बांग्लादेश", "नेपाल", "श्रीलंका", "चीन", "जापान", "रूस", "फ़्रांस", "फ्रांस",
                "जर्मनी", "इटली", "स्पेन", "ब्राज़ील", "कनाडा", "ऑस्ट्रेलिया", "इंग्लैंड", "अमेरिका", "मिस्र", "ईरान"]
# spellings of the same name must not replace each other
_SAME = [{"झारखंड", "झारखण्ड"}, {"मिज़ोरम", "मिजोरम"}, {"तमिलनाडु", "तमिल नाडु"}, {"उत्तराखण्ड", "उत्तराखंड"},
         {"चण्डीगढ़", "चंडीगढ़"}, {"फ़्रांस", "फ्रांस"}]


def _same(a: str, b: str) -> bool:
    return a == b or any(a in s and b in s for s in _SAME)


def swap_place(sentence: str, rng: random.Random) -> tuple[str, str, str] | None:
    """(new sentence, old name, new name) with the first listed state/country name replaced, or None."""
    for names in (HI_STATES, HI_COUNTRIES):
        # whole words only: "भारत" in "भारतीय" (Indian) is not the country name
        found = []
        for n in sorted(names, key=len, reverse=True):
            m = re.search(rf"(?:^|(?<=[\s(,]))({re.escape(n)})(?=[\s,।.!?)]|$)", sentence)
            if m:
                found.append((m.start(1), n))
        if found:
            pos, old = min(found)
            new = rng.choice([n for n in names if not _same(n, old) and n not in sentence])
            return sentence[:pos] + new + sentence[pos + len(old):], old, new
    return None


def build_hiwiki_swap() -> None:
    rng = random.Random(SEED)
    rows = []
    for split in ("dev", "test"):
        d = pd.read_csv(OUT / f"hiwiki_{split}.csv", encoding="utf-8", dtype=str)
        for r in d[d.label == "Verified"].itertuples():
            got = swap_place(r.text, rng)
            if not got:
                continue
            text, old, new = got
            rows.append({"item_id": r.item_id.replace("-t", "-s"), "set": "hiwiki_swap", "split": split, "language": "hi",
                         "text": text, "label": "false", "meta": json.dumps({"from": old, "to": new}, ensure_ascii=False)})
    save(rows, "hiwiki_swap")


# ---------------------------------------------------------------- 4c. TruthfulQA (misconceptions)
def build_truthfulqa() -> None:
    from member3_backend.claim_extractor import is_well_formed_claim, not_a_claim
    d = pd.read_parquet(DATA / "truthfulqa_generation.parquet")
    rng = random.Random(SEED)
    order = list(range(len(d)))
    rng.shuffle(order)
    dev_q = set(order[: len(order) // 2])

    def usable(t: str) -> str | None:
        t = " ".join(str(t).split()).strip()
        if not t or "no comment" in t.lower() or not 4 <= len(t.split()) <= 40:
            return None
        t = t if t[-1] in ".!?" else t + "."
        return t if is_well_formed_claim(t, "en") and not not_a_claim(t, "en") else None

    rows = []
    for i, r in enumerate(d.itertuples()):
        split = "dev" if i in dev_q else "test"
        for kind, text in (("true", r.best_answer), ("false", (list(r.incorrect_answers) or [""])[0])):
            t = usable(text)
            if t:
                rows.append({"item_id": f"tqa-{i:03d}-{kind[0]}", "set": "truthfulqa", "split": split, "language": "en",
                             "text": t, "label": kind, "meta": json.dumps({"question": r.question, "category": r.category})})
    save(rows, "truthfulqa")


# ---------------------------------------------------------------- 5. v1 gold (secondary)
def build_v1gold() -> None:
    rows = []
    for split, fname in (("dev", "gold_train_clean.csv"), ("test", "gold_test_clean.csv")):
        d = pd.read_csv(ROOT / fname, encoding="utf-8")
        d = d[d.gold_verdict.isin(["Verified", "Hallucinated"])]
        rows += [{"item_id": r.claim_id, "set": "v1gold", "split": split, "language": r.language, "text": r.claim_text,
                  "label": "true" if r.gold_verdict == "Verified" else "false", "meta": ""} for r in d.itertuples()]
    save(rows, "v1gold")


BUILDERS = {"mushroom": build_mushroom, "fever": build_fever, "xfact": build_xfact, "hiwiki": build_hiwiki,
            "hiwiki_swap": build_hiwiki_swap, "truthfulqa": build_truthfulqa, "v1gold": build_v1gold}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name in sys.argv[1:] or list(BUILDERS):
        print(f"== {name}")
        BUILDERS[name]()
