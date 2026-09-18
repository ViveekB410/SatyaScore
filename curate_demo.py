"""Runs candidate demo claims through /detect and reports which ones the model
scores correctly + confidently, so we can hand the frontend a reliable list.
Slow on CPU (~40s/claim) — patient by design."""
import sys
from fastapi.testclient import TestClient
from member3_backend.api import app

H = {"X-API-Key": "dev-key-satyascore-2026"}

# (language, text, expected_verdict)
CANDIDATES = [
    ("en", "The capital of France is Paris.", "Verified"),
    ("en", "Water is composed of hydrogen and oxygen.", "Verified"),
    ("en", "The Indian Premier League is a professional cricket league in India.", "Verified"),
    ("en", "Dengue fever is transmitted to humans by mosquitoes.", "Verified"),
    ("en", "Mahatma Gandhi was a leader of the Indian independence movement.", "Verified"),
    ("en", "The Taj Mahal is located in Agra, India.", "Verified"),
    ("en", "The capital of Japan is Beijing.", "Hallucinated"),
    ("en", "Dengue fever is a type of bone cancer.", "Hallucinated"),
    ("en", "Paris is the capital of Germany.", "Hallucinated"),
    ("en", "The Sun revolves around the Earth.", "Hallucinated"),
    ("en", "The Taj Mahal is located in France.", "Hallucinated"),
    ("hi", "पेरिस फ्रांस की राजधानी है।", "Verified"),
    ("hi", "ताजमहल भारत में स्थित है।", "Verified"),
    ("hi", "क्रिकेट भारत में एक लोकप्रिय खेल है।", "Verified"),
    ("hi", "जापान की राजधानी बीजिंग है।", "Hallucinated"),
    ("hi", "ताजमहल फ्रांस में स्थित है।", "Hallucinated"),
]


def out(s):
    sys.stdout.buffer.write((s + "\n").encode("utf-8")); sys.stdout.flush()


def main():
    good = []
    with TestClient(app) as c:
        out(f"index size: {c.get('/health').json()['index_size']}")
        for i, (lang, text, exp) in enumerate(CANDIDATES, 1):
            r = c.post("/detect", json={"text": text, "language": lang}, headers=H).json()
            cl = r["claims"][0]
            got, score = cl["verdict"], cl["hallu_score"]
            confident = (exp == "Verified" and got == "Verified" and score >= 0.65) or \
                        (exp == "Hallucinated" and got == "Hallucinated" and score <= 0.35)
            mark = "GOOD" if confident else ("ok  " if got == exp else "MISS")
            out(f"[{i:2d}/{len(CANDIDATES)}] {mark} exp={exp:12s} got={got:12s} score={score:.3f} | [{lang}] {text}")
            if confident:
                good.append((lang, text, exp, score))
    out("\n===== RELIABLE DEMO CLAIMS (correct + confident) =====")
    for lang, text, exp, score in good:
        out(f"  [{lang}] ({exp}, {score:.2f})  {text}")
    out(f"\n{len(good)}/{len(CANDIDATES)} scored correctly and confidently.")


if __name__ == "__main__":
    main()
