"""Local filesystem blob storage (swap for S3/MinIO in production)."""

from __future__ import annotations

from pathlib import Path

from liveness.config import get_settings


class BlobStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or get_settings().storage_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, data: bytes) -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        path = self.root / key
        if not path.exists():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def path_for(self, key: str) -> Path:
        return self.root / key
