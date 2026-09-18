from member3_backend.faiss_retriever import FAISSRetriever, RetrievalResult, RetrievedPassage
from member3_backend.pipeline import DetectionPipeline, PipelineResult

# Note: api.py is NOT imported here — it depends on fastapi/uvicorn and
# instantiates the embedder/retriever/scorer at import time. Import it
# directly (from member3_backend.api import app) when actually serving
# the API, e.g. via `uvicorn member3_backend.api:app`.

__all__ = [
    "FAISSRetriever",
    "RetrievalResult",
    "RetrievedPassage",
    "DetectionPipeline",
    "PipelineResult",
]
