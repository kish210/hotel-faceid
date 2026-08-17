from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..schemas import FaceSearchResult
from ..security import get_current_user
from ..services import face_search
from ..services.audit import log_action

router = APIRouter(prefix="/api/faces", tags=["faces"])


@router.post("/search", response_model=FaceSearchResult)
def search_by_photo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FaceSearchResult:
    """Find a guest by uploading their photo.

    The image is sent to face-service for an embedding, then matched against
    stored face vectors. `matches` is ordered by similarity (descending).
    """
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        matches, quality = face_search.search_guests(db, data, file.content_type or "image/jpeg")
    except face_search.FaceSearchError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    log_action(
        db,
        user,
        "face_search",
        entity="photo",
        detail={"matches": [str(m.person_id) for m in matches]},
    )
    return FaceSearchResult(source_quality=quality, matches=matches)
