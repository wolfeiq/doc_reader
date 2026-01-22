from __future__ import annotations
import logging
from typing import Any
from uuid import UUID
import chromadb
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
    """Base exception for search service errors."""


class EmbeddingError(SearchServiceError):
    """Error generating embeddings."""


class VectorStoreError(SearchServiceError):
    """Error interacting with vector store."""


class SearchService:
    def __init__(self) -> None:
        self._openai = AsyncOpenAI(api_key=settings.openai_api_key)
        self._chroma: chromadb.HttpClient | None = None
        self._collection: chromadb.Collection | None = None
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
                input=text[:8000],  # Truncate to avoid token limits
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
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = [t[:8000] for t in texts[i : i + batch_size]]
            response = await self._openai.embeddings.create(
                model=settings.openai_embedding_model,
                input=batch,
            )
            embeddings.extend([d.embedding for d in response.data])
        return embeddings

    async def add_section(
        self,
        section_id: str | UUID,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        self._ensure_initialized()

        section_id_str = str(section_id)
        embedding = await self._get_embedding(content)

        clean_meta = {}
        if metadata:
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
                elif v is not None:
                    clean_meta[k] = str(v)

        try:
            self._collection.upsert(
                ids=[section_id_str],
                embeddings=[embedding],
                documents=[content],
                metadatas=[clean_meta] if clean_meta else None,
            )
            logger.debug(f"Added section {section_id_str} to vector store")
            return section_id_str
        except ChromaError as e:
            raise VectorStoreError(f"Failed to add section: {e}") from e

    async def add_sections_batch(
        self,
        sections: list[dict[str, Any]],
    ) -> int:
        
        self._ensure_initialized()

        if not sections:
            return 0

        ids = [str(s["section_id"]) for s in sections]
        contents = [s["content"] for s in sections]
        embeddings = await self._get_embeddings_batch(contents)

        metadatas = []
        for s in sections:
            meta = s.get("metadata", {})
            clean = {
                k: str(v) if not isinstance(v, (str, int, float, bool)) else v
                for k, v in meta.items()
                if v is not None
            }
            metadatas.append(clean)

        try:
            self._collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=contents,
                metadatas=metadatas,
            )
            logger.info(f"Batch added {len(sections)} sections")
            return len(sections)
        except ChromaError as e:
            raise VectorStoreError(f"Batch add failed: {e}") from e

    async def search(
        self,
        query: str,
        n_results: int = 10,
        file_path_filter: str | None = None,
        document_id_filter: str | None = None,
        min_score: float | None = None,
    ) -> list[dict[str, Any]]:
        """Search for sections matching a query."""
        self._ensure_initialized()

        query_embedding = await self._get_embedding(query)
        where = self._build_where_clause(file_path_filter, document_id_filter)

        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=min(n_results, 20),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except ChromaError as e:
            raise VectorStoreError(f"Search failed: {e}") from e

        return self._format_results(results, min_score)

    def _build_where_clause(
        self,
        file_path_filter: str | None,
        document_id_filter: str | None,
    ) -> dict | None:
        clauses = []
        if file_path_filter:
            clauses.append({"file_path": {"$contains": file_path_filter}})
        if document_id_filter:
            clauses.append({"document_id": document_id_filter})

        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    def _format_results(
        self,
        results: dict,
        min_score: float | None,
    ) -> list[dict[str, Any]]:
        formatted = []

        if not results["ids"] or not results["ids"][0]:
            return formatted

        for i, section_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i] if results["distances"] else 0
            score = 1 - distance  # Convert distance to similarity

            if min_score and score < min_score:
                continue

            formatted.append({
                "section_id": section_id,
                "content": results["documents"][0][i] if results["documents"] else None,
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "score": round(score, 4),
            })

        logger.debug(f"Search returned {len(formatted)} results")
        return formatted

    async def delete_section(self, section_id: str | UUID) -> bool:
        self._ensure_initialized()

        try:
            self._collection.delete(ids=[str(section_id)])
            logger.debug(f"Deleted section {section_id}")
            return True
        except ChromaError as e:
            logger.error(f"Failed to delete section {section_id}: {e}")
            return False

    async def delete_by_document(self, document_id: str | UUID) -> int:
        self._ensure_initialized()

        try:
            results = self._collection.get(
                where={"document_id": str(document_id)},
                include=[],
            )

            if results["ids"]:
                self._collection.delete(ids=results["ids"])
                logger.info(f"Deleted {len(results['ids'])} sections for document {document_id}")
                return len(results["ids"])
            return 0
        except ChromaError as e:
            logger.error(f"Failed to delete document sections: {e}")
            return 0

    def get_collection_stats(self) -> dict[str, Any]:
        try:
            self._ensure_initialized()
            return {
                "name": settings.chroma_collection_name,
                "count": self._collection.count(),
                "initialized": True,
            }
        except Exception:
            return {
                "name": settings.chroma_collection_name,
                "count": 0,
                "initialized": False,
            }

    def clear_collection(self) -> None:
        self._ensure_initialized()

        results = self._collection.get(include=[])
        if results["ids"]:
            self._collection.delete(ids=results["ids"])
        logger.info("Collection cleared")

    async def initialize(self) -> None:
        self._ensure_initialized()

    async def close(self) -> None:
        self._initialized = False
        self._chroma = None
        self._collection = None


search_service = SearchService()