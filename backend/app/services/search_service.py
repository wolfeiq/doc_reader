"""
Search Service - Vector Similarity Search with ChromaDB
========================================================

This service provides semantic search capabilities using vector embeddings.
Documents are embedded using OpenAI's embedding model and stored in ChromaDB.

How Vector Search Works:
------------------------
1. Document sections are converted to vectors (embeddings) using OpenAI
2. Vectors are stored in ChromaDB with metadata
3. Search queries are also converted to vectors
4. ChromaDB finds sections with similar vectors (cosine similarity)

Why ChromaDB?
-------------
- Easy self-hosted setup (runs as Docker container)
- Good performance for small-medium datasets (<1M vectors)
- Simple HTTP API
- Supports metadata filtering

Production Alternatives:
------------------------
For larger scale or managed service, consider:
- Pinecone: Fully managed, excellent scaling
- Weaviate: Open source, good hybrid search
- Qdrant: High performance, Rust-based
- pgvector: PostgreSQL extension (keeps everything in one DB)

Cost Considerations:
--------------------
- OpenAI embeddings: ~$0.00002 per 1K tokens (text-embedding-3-small)
- A typical doc section is ~500 tokens = $0.00001 per section
- 10K sections = ~$0.10 to embed
- Consider batching embeddings and caching frequently searched queries

Production Considerations:
--------------------------
- Implement embedding cache (Redis) for repeated content
- Add retry logic for OpenAI API failures (already done via tenacity)
- Monitor ChromaDB memory usage
- Consider async embedding generation for bulk imports
- Add embedding version tracking for model upgrades
"""

from __future__ import annotations
import logging
from typing import Any, TypedDict, NotRequired
from uuid import UUID


class SearchResultDict(TypedDict):
    """Type definition for search results returned by the service."""
    section_id: str
    content: str | None
    metadata: dict[str, Any]
    score: float  # 0.0-1.0, higher is more similar


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
        where: dict[str, Any] | None = None,
        file_path_filter: str | None = None,
        document_id_filter: str | None = None,
        min_score: float | None = None,
    ) -> list[SearchResultDict]:
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
    ) -> list[SearchResultDict]:
        return await self.search(
            query=query, 
            n_results=n_results,
            where={"file_path": {"$eq": path_pattern}} 
        )

    def _format_results(
        self,
        results: dict[str, Any],
        min_score: float | None,
    ) -> list[SearchResultDict]:
        formatted: list[SearchResultDict] = []

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

    def list_all_ids(self) -> list[str]:
        """Return all embedding IDs in the collection."""
        self._ensure_initialized()
        if self._collection is None:
            return []
        results = self._collection.get(include=[])
        return results.get("ids", [])

    def delete_ids(self, ids: list[str]) -> int:
        """Delete embeddings by IDs. Returns count of deleted."""
        if not ids:
            return 0
        self._ensure_initialized()
        if self._collection is None:
            return 0
        self._collection.delete(ids=ids)
        return len(ids)

    async def delete_by_document(self, document_id: str) -> int:
        """
        Delete all embeddings belonging to a specific document.

        Args:
            document_id: The document UUID to delete embeddings for

        Returns:
            Number of embeddings deleted
        """
        self._ensure_initialized()
        if self._collection is None:
            return 0

        # Find all embeddings with this document_id in metadata
        results = self._collection.get(
            where={"document_id": {"$eq": document_id}},
            include=[]
        )

        ids_to_delete = results.get("ids", [])
        if ids_to_delete:
            self._collection.delete(ids=ids_to_delete)
            logger.info(f"Deleted {len(ids_to_delete)} embeddings for document {document_id}")

        return len(ids_to_delete)

    async def initialize(self) -> None:
        self._ensure_initialized()

    async def close(self) -> None:
        self._initialized = False
        self._chroma = None
        self._collection = None

search_service = SearchService()