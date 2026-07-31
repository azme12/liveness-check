"""1:N face gallery — InsightFace embeddings (Face Recognition System pattern).

The external Face_Recognition_System project uses MobileFace + index.bin on disk.
We use the same cosine-threshold idea but store embeddings in MongoDB and reuse
InsightFace so scores stay compatible with identity_check face matching.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from liveness.config import get_settings
from liveness.db import find_one, get_database
from liveness.ml.face import FaceAnalyzer, get_face_analyzer
from liveness.types import new_id, utc_now


@dataclass
class GalleryMatch:
    client_id: str
    label: str
    score: float
    passed: bool
    embedding_id: str


@dataclass
class GalleryEnrollResult:
    embedding_id: str
    client_id: str
    label: str
    backend: str


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float32).flatten()
    b = np.asarray(b, dtype=np.float32).flatten()
    denom = float(np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8
    return float(np.dot(a, b) / denom)


class FaceGallery:
    """Enroll and search face embeddings per client (1:N within client scope)."""

    def __init__(self, analyzer: FaceAnalyzer | None = None) -> None:
        self.analyzer = analyzer or get_face_analyzer()
        self.threshold = get_settings().face_gallery_threshold

    def embed_image(self, image: np.ndarray) -> tuple[np.ndarray | None, str]:
        faces = self.analyzer.detect(image)
        if not faces:
            return None, self.analyzer._backend
        face = faces[0]
        if face.embedding is not None:
            return face.embedding, self.analyzer._backend
        return self.analyzer._embedding_fallback(image, face), f"{self.analyzer._backend}_fallback"

    async def enroll(
        self,
        *,
        client_id: str,
        image: np.ndarray,
        label: str | None = None,
        source_id: str | None = None,
    ) -> GalleryEnrollResult:
        embedding, backend = self.embed_image(image)
        if embedding is None:
            raise ValueError("No face detected in enrollment image")

        doc: dict[str, Any] = {
            "id": new_id("femb_"),
            "client_id": client_id,
            "label": label or client_id,
            "embedding": embedding.tolist(),
            "source_id": source_id,
            "backend": backend,
            "created_at": utc_now(),
        }
        await get_database().face_embeddings.insert_one(doc)
        return GalleryEnrollResult(
            embedding_id=doc["id"],
            client_id=client_id,
            label=doc["label"],
            backend=backend,
        )

    async def search_client(
        self,
        *,
        client_id: str,
        image: np.ndarray,
    ) -> GalleryMatch | None:
        """Match a selfie against all embeddings enrolled for this client."""
        embedding, _ = self.embed_image(image)
        if embedding is None:
            return None

        cursor = get_database().face_embeddings.find({"client_id": client_id}, {"_id": 0})
        best: GalleryMatch | None = None
        async for row in cursor:
            stored = np.asarray(row["embedding"], dtype=np.float32)
            score = _cosine(embedding, stored)
            passed = score >= self.threshold
            candidate = GalleryMatch(
                client_id=client_id,
                label=row.get("label") or client_id,
                score=score,
                passed=passed,
                embedding_id=row["id"],
            )
            if best is None or candidate.score > best.score:
                best = candidate
        return best

    async def has_enrollment(self, client_id: str) -> bool:
        doc = await find_one("face_embeddings", {"client_id": client_id})
        return doc is not None
