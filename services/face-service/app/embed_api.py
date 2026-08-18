"""Small HTTP API that turns an uploaded photo into a face embedding.

Used by the backend for photo-based guest search. It runs as a separate
thread so the capture supervisor keeps running untouched.
"""

import logging
import threading

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile
from pydantic import BaseModel

from .face_engine import FaceEngine

log = logging.getLogger(__name__)

_LOCK = threading.Lock()


class EmbedResult(BaseModel):
    embedding: list[float]
    quality: float
    det_score: float
    gender: str | None = None
    age: int | None = None


def build_embed_app(engine: FaceEngine) -> FastAPI:
    app = FastAPI(title="face-service embed")

    @app.post("/embed", response_model=EmbedResult)
    def embed(file: UploadFile) -> EmbedResult:
        data = file.file.read()
        frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(status_code=400, detail="Not a decodable image")

        # Frame-by-frame workers already hold no lock; a burst of embed calls
        # must not race the ONNX runtime either.
        with _LOCK:
            faces = engine.detect(frame)

        if not faces:
            raise HTTPException(status_code=422, detail="No face found in image")

        # Largest face wins — the photo is usually a single person.
        faces.sort(key=lambda f: f.bbox[2] * f.bbox[3], reverse=True)
        face = faces[0]

        return EmbedResult(
            embedding=face.embedding,
            quality=face.quality,
            det_score=face.det_score,
            gender=face.gender,
            age=face.age,
        )

    return app
