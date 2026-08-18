"""Photo-based guest search: forward the photo to face-service for an
embedding, then run the same cosine-match query used at the door."""

from __future__ import annotations

import logging
from typing import Any

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import FaceEmbedding, PersonRole
from ..schemas import FaceSearchMatch
from .vector_search import top_matches

log = logging.getLogger(__name__)

SEARCH_LIMIT = 10
MIN_SIMILARITY = 0.20


class FaceSearchError(Exception):
    """Raised when the embedding service cannot process the request."""


def embed_photo(data: bytes, content_type: str) -> dict[str, Any] | None:
    """Ask face-service to build a face vector from an uploaded photo.

    Returns the embedding payload, or None when the photo contained no
    usable face. Raises FaceSearchError when the service is unreachable.
    """
    try:
        response = requests.post(
            f"{settings.face_service_url}/embed",
            files={"file": ("photo", data, content_type)},
            timeout=30,
        )
    except requests.RequestException:
        log.warning("face-service is unreachable at %s", settings.face_service_url, exc_info=True)
        raise FaceSearchError("سرویس تشخیص چهره در دسترس نیست") from None

    if response.status_code == 422:
        return None  # image decoded, but no face found
    if response.status_code != 200:
        log.warning("face-service embed failed with status %s", response.status_code)
        raise FaceSearchError("سرویس تشخیص چهره در دسترس نیست")
    return response.json()


def search_guests(
    db: Session, data: bytes, content_type: str
) -> tuple[list[FaceSearchMatch], float | None]:
    result = embed_photo(data, content_type)
    if result is None:
        return [], None

    ranked = top_matches(db, result["embedding"], SEARCH_LIMIT)
    matches: list[FaceSearchMatch] = []
    for face, dist in ranked:
        similarity = 1.0 - dist
        if similarity < MIN_SIMILARITY:
            continue
        person = face.person
        matches.append(
            FaceSearchMatch(
                person_id=person.id,
                display_name=person.display_name,
                role=person.role,
                room_number=person.room_number,
                reference_image=person.reference_image,
                similarity=round(similarity, 4),
            )
        )
    return matches, result.get("quality")
