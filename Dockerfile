# SatyaScore API — containerized (FR: portability / one-command deploy).
# Self-contained: bakes the spaCy + HuggingFace models into the image so the
# container runs offline. Image is large (~3-4GB) because of torch + the NLI /
# embedding models — that's expected for an ML service.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_sm

# Pre-download the models used at request time so the container needs no
# network at runtime (XLM-R embedder + mDeBERTa NLI; MuRIL fetched lazily only
# for transliterated Hindi).
RUN python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('sentence-transformers/paraphrase-xlm-r-multilingual-v1'); \
from transformers import AutoTokenizer, AutoModelForSequenceClassification; \
AutoTokenizer.from_pretrained('MoritzLaurer/mDeBERTa-v3-base-mnli-xnli'); \
AutoModelForSequenceClassification.from_pretrained('MoritzLaurer/mDeBERTa-v3-base-mnli-xnli')"

# Application code
COPY member1_model ./member1_model
COPY member2_data ./member2_data
COPY member3_backend ./member3_backend
# Runtime artifacts: the cached bilingual corpus + trained weights the API loads at startup.
# The API prefers the bigger demo corpus (corpus_*_demo.*) when present.
COPY corpus_passages.json corpus_vectors.npy weights_en.json weights_hi.json ./
COPY corpus_passages_demo.json corpus_vectors_demo.npy ./

ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
EXPOSE 8000

CMD ["uvicorn", "member3_backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
