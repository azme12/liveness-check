"""1:N face gallery — InsightFace or SFace embeddings stored in MongoDB."""

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
        sface = self.analyzer._sface_embedding(image, face)
        if sface is not None:
            return sface, "opencv_sface"
        return None, "sface_required"

    async def search_client(
        self,
        *,
        client_id: str,
        image: np.ndarray,
    ) -> GalleryMatch | None:
        embedding, _ = self.embed_image(image)
        if embedding is None:
            return None
        return await self._search_embeddings(embedding, query={"client_id": client_id})

    async def search_duplicates(
        self,
        *,
        org_id: str,
        image: np.ndarray,
        exclude_client_id: str | None = None,
        threshold: float | None = None,
    ) -> GalleryMatch | None:
        embedding, _ = self.embed_image(image)
        if embedding is None:
            return None
        query: dict[str, Any] = {"org_id": org_id}
        if exclude_client_id:
            query["client_id"] = {"$ne": exclude_client_id}
        return await self._search_embeddings(embedding, query=query, threshold=threshold)

    async def _search_embeddings(
        self,
        embedding: np.ndarray,
        *,
        query: dict[str, Any],
        threshold: float | None = None,
    ) -> GalleryMatch | None:
        thr = self.threshold if threshold is None else threshold
        cursor = get_database().face_embeddings.find(query, {"_id": 0})
        best: GalleryMatch | None = None
        async for row in cursor:
            stored = np.asarray(row["embedding"], dtype=np.float32)
            if stored.shape != embedding.shape:
                continue
            score = _cosine(embedding, stored)
            candidate = GalleryMatch(
                client_id=row.get("client_id") or "",
                label=row.get("label") or row.get("client_id") or "",
                score=score,
                passed=score >= thr,
                embedding_id=row["id"],
            )
            if best is None or candidate.score > best.score:
                best = candidate
        return best

    async def enroll(
        self,
        *,
        client_id: str,
        image: np.ndarray,
        label: str | None = None,
        source_id: str | None = None,
        org_id: str | None = None,
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
        if org_id:
            doc["org_id"] = org_id
        await get_database().face_embeddings.insert_one(doc)
        return GalleryEnrollResult(
            embedding_id=doc["id"],
            client_id=client_id,
            label=doc["label"],
            backend=backend,
        )

    async def has_enrollment(self, client_id: str) -> bool:
        doc = await find_one("face_embeddings", {"client_id": client_id})
        return doc is not None

    async def ensure_enrolled(
        self,
        *,
        client_id: str,
        org_id: str,
        image: np.ndarray,
        source_id: str | None = None,
        label: str | None = None,
    ) -> GalleryEnrollResult | None:
        if await self.has_enrollment(client_id):
            return None
        try:
            return await self.enroll(
                client_id=client_id,
                org_id=org_id,
                image=image,
                source_id=source_id,
                label=label,
            )
        except ValueError:
            return None
