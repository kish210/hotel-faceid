"""Pure-Python (numpy) cosine search over stored face vectors.

Replaces PostgreSQL/pgvector so the whole stack runs on SQLite — the face
list at hotel scale fits trivially in memory and a matrix multiply is fast.
"""

from __future__ import annotations

import numpy as np


def cosine_similarities(query: list[float], vectors: list[list[float]]) -> np.ndarray:
    """Cosine similarity from ``query`` to every row in ``vectors`` (0..1)."""
    q = np.asarray(query, dtype=np.float32).ravel()
    m = np.asarray(vectors, dtype=np.float32)
    qn = np.linalg.norm(q)
    mn = np.linalg.norm(m, axis=1)
    dots = m @ q
    with np.errstate(divide="ignore", invalid="ignore"):
        sims = dots / (mn * qn + 1e-9)
        sims[mn == 0] = 0.0
    return sims


def nearest(query: list[float], vectors: list[list[float]]) -> tuple[int, float]:
    """Index of the closest vector and its similarity, or (-1, 0.0)."""
    if not vectors:
        return -1, 0.0
    sims = cosine_similarities(query, vectors)
    idx = int(np.argmax(sims))
    return idx, float(sims[idx])