"""Portable nearest-neighbour face matching.

Stored embeddings live in a portable JSON column (works on SQLite and
Postgres without pgvector), so the ANN query is done in-process with numpy
instead of a SQL operator. Fine for the bundled-single-install scale of a
hotel (a few thousand reference vectors → a few milliseconds per scan).
"""

from __future__ import annotations

import logging

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import FaceEmbedding, Person

log = logging.getLogger(__name__)

MAX_CANDIDATES = 50


def _candidates(db: Session | None = None) -> list[tuple[FaceEmbedding, float]]:
    """Load (face, distance) pairs ordered by cosine distance from `query`.

    Distance is 1 - cosine similarity over the full 512-dim vector.
    """
    rows = db.execute(
        select(FaceEmbedding, Person.id)
        .join(Person, Person.id == FaceEmbedding.person_id)
        .where(Person.deleted_at.is_(None), Person.merged_into.is_(None))
    ).all()
    return [(face, person_id) for face, person_id in rows]


def nearest(
    query: list[float],
    faces: list[tuple[FaceEmbedding, object]],
) -> list[tuple[FaceEmbedding, float]]:
    """Rank `faces` by cosine distance to `query`, ascending."""
    if not faces:
        return []
    q = np.asarray(query, dtype=np.float64).reshape(1, -1)
    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        return []
    q = q / q_norm

    matrix = np.array([row[0].embedding for row in faces], dtype=np.float64)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix = matrix / norms

    distances = 1.0 - (matrix @ q.T).ravel()
    order = np.argsort(distances)
    return [(faces[i][0], float(distances[i])) for i in order]


def find_match(db: Session, embedding: list[float]) -> tuple[Person | None, float | None]:
    """Nearest neighbour search over stored face vectors (cosine distance)."""
    candidates = _candidates(db)
    if not candidates:
        return None, None

    ranked = nearest(embedding, candidates)
    if not ranked:
        return None, None

    face, dist = ranked[0]
    similarity = 1.0 - dist
    if similarity < settings.face_match_threshold:
        return None, similarity
    return face.person, similarity


def top_matches(db: Session, embedding: list[float], limit: int) -> list[tuple[FaceEmbedding, float]]:
    """Top-`limit` matches descending by similarity, for photo search."""
    candidates = _candidates(db)
    if not candidates:
        return []
    return nearest(embedding, candidates)[:limit]