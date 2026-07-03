"""BGE-M3 embeddings + Qdrant vector store (guarded)."""
from __future__ import annotations

import uuid

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)
_embedder = None

EMBED_DIM = 1024  # BGE-M3 dense dimension


class BGEEmbedder:
    def available(self) -> bool:
        if not (settings.ai_enabled and settings.embeddings_enabled):
            return False
        try:
            import FlagEmbedding  # noqa: F401

            return True
        except Exception:  # noqa: BLE001
            log.warning("embeddings unavailable: FlagEmbedding not installed")
            return False

    def _load(self):
        global _embedder
        if _embedder is None:
            from FlagEmbedding import BGEM3FlagModel

            _embedder = BGEM3FlagModel(settings.embed_model, use_fp16=False)
        return _embedder

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        out = model.encode(texts, batch_size=8, max_length=512)["dense_vecs"]
        return [v.tolist() for v in out]


class QdrantVectors:
    def __init__(self) -> None:
        self.collection = f"{settings.qdrant_collection_prefix}_evidence"

    def available(self) -> bool:
        if not (settings.ai_enabled and settings.embeddings_enabled):
            return False
        try:
            import qdrant_client  # noqa: F401

            return True
        except Exception:  # noqa: BLE001
            log.warning("qdrant client not installed")
            return False

    def _client(self):
        from qdrant_client import QdrantClient

        return QdrantClient(url=settings.qdrant_url)

    def ensure_collection(self) -> None:
        from qdrant_client.models import Distance, VectorParams

        client = self._client()
        existing = {c.name for c in client.get_collections().collections}
        if self.collection not in existing:
            client.create_collection(
                self.collection,
                vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
            )

    def upsert(self, vectors: list[list[float]], payloads: list[dict]) -> list[str]:
        from qdrant_client.models import PointStruct

        client = self._client()
        ids = [str(uuid.uuid4()) for _ in vectors]
        points = [
            PointStruct(id=pid, vector=vec, payload=pl)
            for pid, vec, pl in zip(ids, vectors, payloads, strict=True)
        ]
        client.upsert(self.collection, points=points)
        return ids


def get_embedder() -> BGEEmbedder | None:
    c = BGEEmbedder()
    return c if c.available() else None


def get_vectors() -> QdrantVectors | None:
    c = QdrantVectors()
    return c if c.available() else None
