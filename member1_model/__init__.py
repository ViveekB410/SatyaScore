# Note: embeddings.py pulls in sentence-transformers/torch model downloads,
# so it's intentionally NOT imported here eagerly — import it directly
# (from member1_model.embeddings import CrossLingualEmbedder) where needed,
# e.g. in the retrieval/API layer. Keeps `import member1_model` cheap for
# anything that only needs the scorer (tests, weight training, etc.).
from member1_model.cmhsa import CMHSAScorer, ClaimSubScores, ClaimScore, Verdict

__all__ = [
    "CMHSAScorer",
    "ClaimSubScores",
    "ClaimScore",
    "Verdict",
]
