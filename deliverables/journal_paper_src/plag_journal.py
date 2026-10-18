"""Word-sequence overlap check for the current deliverables.
A run of N identical consecutive words (N = 8, then 6) shared with a source counts as a match.
Sources: titles + abstracts of the cited papers (arXiv), full texts of 13 cited papers, and the group's own earlier
documents (original synopsis, PRD), reported separately because overlap with your own earlier work is not plagiarism."""
import json, re, sys, zipfile
from pathlib import Path

import requests
import xml.etree.ElementTree as ET
from pdfminer.high_level import extract_text

DOCGEN = Path(r"C:\Users\vivek\AppData\Local\Temp\claude\C--Users-vivek-Downloads-satyascore\d71aa683-7da1-4331-a85a-d3a2236a7da7\scratchpad\docgen2")
REPO = Path(r"C:\Users\vivek\Downloads\satyascore")
OUT = Path(sys.argv[1])

tok = lambda s: re.findall(r"[a-z0-9]+", s.lower())

def docx_text(path, start=None, end=None):
    x = zipfile.ZipFile(path).read("word/document.xml").decode("utf8")
    text = " ".join(re.sub(r"<[^>]+>", "", p) for p in re.findall(r"<w:p[ >].*?</w:p>", x, re.S))
    text = text.replace("&amp;", "&")
    a = text.find(start) if start else 0
    b = text.rfind(end) if end else len(text)
    return re.sub(r"\[\d+(?:,\s*\d+)*\]", " ", text[max(a, 0):b if b > 0 else len(text)])

# ---- sources ----
cited = {}
for f in ("abstracts.json", "abstracts_report.json"):
    for k, v in json.load(open(DOCGEN / f, encoding="utf8")).items():
        if k != "agrawal":  # stale entry: a different paper
            cited[f"abstract:{k}"] = v["title"] + ". " + v["abstract"]
new_ids = {"gptoss": "2508.10925", "judge": "2306.05685", "xfact": "2106.09248", "sbert": "1908.10084"}
try:
    xml = requests.get("https://export.arxiv.org/api/query?max_results=10&id_list=" + ",".join(new_ids.values()), timeout=60).content
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for e in ET.fromstring(xml).findall("a:entry", ns):
        aid = e.find("a:id", ns).text.rsplit("/", 1)[-1].split("v")[0]
        key = next((k for k, v in new_ids.items() if v == aid), aid)
        cited[f"abstract:{key}"] = " ".join(e.find("a:title", ns).text.split()) + ". " + " ".join(e.find("a:summary", ns).text.split())
except Exception as ex:
    print("arXiv fetch failed:", ex)
for f in sorted((DOCGEN / "fulltext_cache").glob("*.txt")):
    cited[f"fulltext:{f.stem}"] = f.read_text(encoding="utf8", errors="ignore")
own = {"own: original synopsis (group)": extract_text(str(REPO / "synopsis satyascore finall.pdf")),
       "own: PRD": extract_text(str(REPO / "SatyaScore_PRD_main.pdf"))}

def check(name, text, sources, N):
    new = tok(text)
    total, per = set(), []
    for src, s in sources.items():
        t = tok(s)
        grams = {tuple(t[i:i + N]) for i in range(len(t) - N + 1)}
        hit = set()
        for i in range(len(new) - N + 1):
            if tuple(new[i:i + N]) in grams:
                hit.update(range(i, i + N))
        if hit:
            per.append((len(hit), src, hit))
        total |= hit
    lines = [f"  {N}-word matches: {len(total)} of {len(new)} words = {100 * len(total) / max(len(new), 1):.1f}%"]
    for n, src, hit in sorted(per, reverse=True)[:6]:
        idx = sorted(hit); runs, s, p = [], idx[0], idx[0]
        for i in idx[1:]:
            if i != p + 1:
                runs.append((s, p)); s = i
            p = i
        runs.append((s, p))
        lines.append(f"     {src:36s} {n:4d} words: " + " | ".join(" ".join(new[a:b + 1]) for a, b in runs[:4]))
    return lines, len(new)


for k, v in json.load(open(Path(r"C:\Users\vivek\AppData\Local\Temp\claude\C--Users-vivek-Downloads-satyascore\b17a7cbc-a824-4c06-a936-7931ed0b33c1\scratchpad\jpaper") / "newrefs.json", encoding="utf8")).items():
    cited[f"abstract:{k}"] = v["title"] + ". " + v["abstract"]
D = REPO / "deliverables"
own.update({
    "own: IEEE paper v2": docx_text(D / "SatyaScore_IEEE_Paper_v2.docx"),
    "own: project report (college)": docx_text(D / "SatyaScore_Project_Report_College.docx"),
    "own: results paper": docx_text(D / "SatyaScore_Results.docx"),
    "own: synopsis v2": docx_text(D / "SatyaScore_Synopsis_v2.docx"),
})
paper = docx_text(Path(r"C:\Users\vivek\AppData\Local\Temp\claude\C--Users-vivek-Downloads-satyascore\b17a7cbc-a824-4c06-a936-7931ed0b33c1\scratchpad\jpaper") / "SatyaScore_Journal_Paper.docx", "Chatbots built on large language models", "References")
report = [f"sources: {sum(k.startswith('abstract') for k in cited)} cited-paper abstracts, "
          f"{sum(k.startswith('fulltext') for k in cited)} cited-paper full texts, {len(own)} own earlier documents", "== Journal paper (Abstract to Declarations)"]
for N in (8, 6):
    lines, n = check("paper", paper, cited, N)
    report += [l.replace("matches", "matches with published papers", 1) if i == 0 else l for i, l in enumerate(lines)]
for N in (8,):
    lines, n = check("paper", paper, own, N)
    report += [lines[0].replace("matches", "matches with your own earlier documents", 1)] + lines[1:7]
OUT.write_text(chr(10).join(report), encoding="utf8")
print(chr(10).join(report))
