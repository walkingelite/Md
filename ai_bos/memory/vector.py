"""ChromaDB vector store adapter — semantic search over business knowledge."""

from __future__ import annotations

import uuid

import chromadb
from chromadb.config import Settings as ChromaSettings

from ai_bos.logging_config import log

EMBEDDING_MODEL_VERSION = "v1"


class VectorMemory:
    def __init__(self) -> None:
        self._client: chromadb.AsyncClientAPI | None = None
        self._collection: chromadb.Collection | None = None

    async def initialize(self) -> None:
        self._client = await chromadb.AsyncHttpClient(
            host="localhost",
            port=8000,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = await self._client.get_or_create_collection(
            name=f"aibos_facts_{EMBEDDING_MODEL_VERSION}",
            metadata={"hnsw:space": "cosine"},
        )
        log.info("vector_memory.initialized")

    async def index(
        self,
        *,
        fact_id: uuid.UUID,
        business_id: uuid.UUID,
        text: str,
        metadata: dict,
    ) -> None:
        assert self._collection is not None
        meta = {**metadata, "business_id": str(business_id), "model_version": EMBEDDING_MODEL_VERSION}
        await self._collection.upsert(
            ids=[str(fact_id)],
            documents=[text],
            metadatas=[meta],
        )

    async def search(
        self,
        *,
        query: str,
        business_id: uuid.UUID,
        limit: int = 10,
    ) -> list[str]:
        assert self._collection is not None
        results = await self._collection.query(
            query_texts=[query],
            n_results=limit,
            where={"business_id": str(business_id)},
        )
        ids: list[str] = results["ids"][0] if results["ids"] else []
        return ids
