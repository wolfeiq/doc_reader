from __future__ import annotations
import logging
from typing import Any, cast
from uuid import UUID
import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.errors import ChromaError
from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings

logger = logging.getLogger(__name__)

class SearchServiceError(Exception):
    pass

class EmbeddingError(SearchServiceError):
    pass

class VectorStoreError(SearchServiceError):
    pass

class SearchService:
    def __init__(self) -> None:
        self._openai = AsyncOpenAI(api_key=settings.openai_api_key)
        self._chroma: chromadb.HttpClient | None = None
        self._collection: Collection | None = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        try:
            self._chroma = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
            )
            self._collection = self._chroma.get_or_create_collection(
                name=settings.chroma_collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            self._initialized = True
            logger.info("ChromaDB connection established")
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB: {e}")
            raise VectorStoreError(f"ChromaDB connection failed: {e}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
    )
    async def _get_embedding(self, text: str) -> list[float]:
        try:
            response = await self._openai.embeddings.create(
                model=settings.openai_embedding_model,
                input=text[:8000], 
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise EmbeddingError(f"Failed to generate embedding: {e}") from e

    async def _get_embeddings_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = [t[:8000] for t in texts[i : i + batch_size]]
            response = await self._openai.embeddings.create(
                model=settings.openai_embedding_model,
                input=batch,
            )
            embeddings.extend([d.embedding for d in response.data])
        return embeddings

    async def search(
        self,
        query: str,
        n_results: int = 5,
        where: dict | None = None,
        file_path_filter: str | None = None,
        document_id_filter: str | None = None,
        min_score: float | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_initialized()
        if self._collection is None:
            raise VectorStoreError("Collection not initialized")

        chroma_where = where

        if not chroma_where:
            chroma_where = self._build_where_clause(file_path_filter, document_id_filter)

        query_embedding = await self._get_embedding(query)

        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=min(n_results, 20),
                where=chroma_where,
                include=["documents", "metadatas", "distances"],
            )
            return self._format_results(results, min_score)
        except ChromaError as e:
            logger.error(f"Chroma search failed: {e}")
            raise VectorStoreError(f"Search failed: {e}") from e

    def _build_where_clause(
        self,
        file_path_filter: str | None,
        document_id_filter: str | None,
    ) -> dict[str, Any] | None:
        clauses: list[dict[str, Any]] = []
        
        if file_path_filter:
            clauses.append({"file_path": {"$eq": file_path_filter}})
        if document_id_filter:
            clauses.append({"document_id": {"$eq": str(document_id_filter)}})

        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    async def search_by_file_path(
        self,
        path_pattern: str,
        query: str = "",
        n_results: int = 20
    ) -> list[dict[str, Any]]:
        return await self.search(
            query=query, 
            n_results=n_results,
            where={"file_path": {"$eq": path_pattern}} 
        )

    def _format_results(
        self,
        results: dict[str, Any],
        min_score: float | None,
    ) -> list[dict[str, Any]]:
        formatted: list[dict[str, Any]] = []

        if not results.get("ids") or not results["ids"][0]:
            return formatted

        ids = results["ids"][0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i, section_id in enumerate(ids):
            distance = distances[i] if i < len(distances) else 0.0
            score = 1.0 - distance 

            if min_score is not None and score < min_score:
                continue

            formatted.append({
                "section_id": section_id,
                "content": documents[i] if i < len(documents) else None,
                "metadata": metadatas[i] if i < len(metadatas) else {},
                "score": round(score, 4),
            })

        return formatted
    
    async def add_section(self, section_id: str | UUID, content: str, metadata: dict[str, Any] | None = None) -> str:
        self._ensure_initialized()
        section_id_str = str(section_id)
        embedding = await self._get_embedding(content)
        clean_meta = {k: (str(v) if not isinstance(v, (str, int, float, bool)) else v) for k, v in (metadata or {}).items() if v is not None}
        self._collection.upsert(ids=[section_id_str], embeddings=[embedding], documents=[content], metadatas=[clean_meta] if clean_meta else None)
        return section_id_str

    def get_collection_stats(self) -> dict[str, Any]:
        self._ensure_initialized()
        count = self._collection.count() if self._collection else 0
        return {"name": settings.chroma_collection_name, "count": count, "initialized": self._initialized}

    def clear_collection(self) -> None:
        self._ensure_initialized()
        results = self._collection.get(include=[])
        if results["ids"]: self._collection.delete(ids=results["ids"])

    async def initialize(self) -> None:
        self._ensure_initialized()

    async def close(self) -> None:
        self._initialized = False
        self._chroma = None
        self._collection = None

search_service = SearchService()