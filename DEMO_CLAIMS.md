# SatyaScore — Curated Demo Claims

These claims were **run through the live `/detect` API** (bigger demo corpus, 9,351
passages) and scored **correctly and confidently**. Use these for a demo that
consistently looks right. Language = `en` or `hi`; score is `hallu_score`
(>0.65 → Verified, <0.35 → Hallucinated).

## ✅ True claims → Verified
| Lang | Claim | Score |
|---|---|---|
| en | The capital of France is Paris. | 1.00 |
| en | Water is composed of hydrogen and oxygen. | 0.97 |
| en | The Indian Premier League is a professional cricket league in India. | 0.99 |
| en | Mahatma Gandhi was a leader of the Indian independence movement. | 0.99 |
| hi | पेरिस फ्रांस की राजधानी है। | 1.00 |
| hi | ताजमहल भारत में स्थित है। | 1.00 |
| hi | क्रिकेट भारत में एक लोकप्रिय खेल है। | 0.66 |

## ❌ False claims → Hallucinated
| Lang | Claim | Score |
|---|---|---|
| en | The capital of Japan is Beijing. | 0.19 |
| en | Dengue fever is a type of bone cancer. | 0.02 |
| en | Paris is the capital of Germany. | 0.00 |
| en | The Taj Mahal is located in France. | 0.00 |
| hi | ताजमहल फ्रांस में स्थित है। | 0.00 |

## ⚠️ Do NOT use these in a live demo (the detector mis-scores them)
- "Dengue fever is transmitted to humans by mosquitoes." → **Uncertain** (true, but weak evidence)
- "The Taj Mahal is located in Agra, India." → **Uncertain**
- "The Sun revolves around the Earth." → **Verified** (false, but scored high — an embarrassing miss)
- "जापान की राजधानी बीजिंग है।" (Japan's capital is Beijing) → **Uncertain** (should be Hallucinated)

## Honest note for the demo
The detector is genuinely weak (near-chance discrimination — see `RESULTS_SUMMARY.md`).
These 12 claims are hand-verified to demo well, but on arbitrary user input it *will*
mis-score some claims. Frame the demo as a research prototype of a hard problem, and
prefer curated claims for scripted walkthroughs. Regenerate/extend this list with
`python curate_demo.py` (edit its CANDIDATES).
