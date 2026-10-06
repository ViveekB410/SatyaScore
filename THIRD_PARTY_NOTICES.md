# Third-party components, data and services

SatyaScore's own code is separate from the components below. This list is for copyright registration,
the research paper, and any future release. "Checked" = confirmed at the source on 2026-10-06; other
entries are the projects' published licences.

## Models (downloaded at run time, not part of this repository)

| Model | Use | Licence |
|---|---|---|
| `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` | NLI judge | MIT (checked, model card) |
| `sentence-transformers/paraphrase-xlm-r-multilingual-v1` | embeddings / retrieval | Apache-2.0 (checked, model card) |
| spaCy `en_core_web_sm` | English parsing, entities | MIT |
| `lytang/MiniCheck-DeBERTa-v3-Large` | design probe only, not in the live system | MIT (checked, model card) |

## Libraries

Python: FastAPI, spaCy, FAISS, Indic NLP Library, pdfminer.six (MIT); PyTorch, NumPy, pandas,
scikit-learn (BSD-3-Clause); transformers, sentence-transformers, requests (Apache-2.0).
Web: React, Vite, Tailwind CSS, Radix UI, Framer Motion, React Router, sonner (MIT).
Each library's own licence file is in its package.

## Data and services queried at run time

| Source | What is used | Terms |
|---|---|---|
| **Wikipedia** (English, Hindi) | article text as evidence; passages stored in `corpus_*` files and caches | **CC BY-SA 4.0**: attribution and share-alike apply to the stored text if it is distributed. Each verdict links its article. |
| **Wikidata** | structured facts | CC0 (public domain) |
| **World Bank Open Data** | country statistics | **CC BY 4.0** (checked): credit "The World Bank"; no implied endorsement ([terms](https://datacatalog.worldbank.org/public-licenses)) |
| **WHO Global Health Observatory** | health statistics | **CC BY-NC-SA 3.0 IGO (checked): non-commercial use only**; acknowledge WHO; no implied endorsement ([WHO copyright](https://www.who.int/about/policies/publishing/copyright)). A commercial deployment must turn this source off (or obtain WHO permission). |
| **Google Fact Check Tools API** | fact-check ratings, publisher names and links | Google API Terms of Service ([terms](https://developers.google.com/fact-check/tools/api/terms)); the fact-check articles belong to their publishers. SatyaScore shows only the rating, the publisher and a link. |
| MedlinePlus (built, switched off) | health topic summaries | NLM terms; not used by the live system |
| Groq API (evaluation only) | LLM answers for the test datasets and the LLM-verifier evaluation | Groq terms; model licences of the generating models apply to their outputs |

## Datasets created in this project

The annotated claim sets (`gold_*.csv`, `round3/`) contain chatbot answers generated through the Groq
API and labels by the project's annotators. Before releasing them with the paper, check the terms of the
models that generated the answers.
