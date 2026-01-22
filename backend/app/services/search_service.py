"""Enhanced search service with ChromaDB and metadata filtering."""

import logging
from uuid import UUID

import chromadb
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)


class SearchService:

    def __init__(self):
        self._openai = AsyncOpenAI(api_key=settings.openai_api_key)
        self._chroma = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port
        )
        self._collection = self._chroma.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _get_embedding(self, text: str) -> list[float]:
        response = await self._openai.embeddings.create(
            model=settings.openai_embedding_model,
            input=text
        )
        return response.data[0].embedding

    async def add_section(
        self,
        section_id: str,
        content: str,
        metadata: dict | None = None
    ) -> str:
        
        embedding = await self._get_embedding(content)
        meta = metadata or {}

        clean_meta = {
            k: str(v) if not isinstance(v, (str, int, float, bool)) else v
            for k, v in meta.items()
        }
        
        self._collection.upsert(
            ids=[section_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[clean_meta] if clean_meta else None
        )
        
        logger.info(f"Added section {section_id} to vector store")
        return section_id

    async def search(
        self,
        query: str,
        n_results: int = 10,
        file_path_filter: str | None = None,
        document_id_filter: str | None = None,
        min_score: float | None = None
    ) -> list[dict]:

        query_embedding = await self._get_embedding(query)
        
        where = None
        where_clauses = []
        
        if file_path_filter:
            where_clauses.append({"file_path": {"$contains": file_path_filter}})
        if document_id_filter:
            where_clauses.append({"document_id": document_id_filter})
        
        if len(where_clauses) == 1:
            where = where_clauses[0]
        elif len(where_clauses) > 1:
            where = {"$and": where_clauses}
        
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, 20),  # Cap at 20
            where=where,
            include=["documents", "metadatas", "distances"]
        )
        

        formatted = []
        if results["ids"] and results["ids"][0]:
            for i, section_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0
                score = 1 - distance
                
                if min_score and score < min_score:
                    continue
                
                formatted.append({
                    "section_id": section_id,
                    "content": results["documents"][0][i] if results["documents"] else None,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": round(score, 4)
                })
        
        logger.info(f"Search for '{query[:50]}...' returned {len(formatted)} results")
        return formatted

    async def search_by_file_path(self, path_pattern: str, n_results: int = 50) -> list[dict]:
        results = self._collection.get(
            where={"file_path": {"$contains": path_pattern}},
            limit=n_results,
            include=["documents", "metadatas"]
        )
        
        formatted = []
        if results["ids"]:
            for i, section_id in enumerate(results["ids"]):
                formatted.append({
                    "section_id": section_id,
                    "content": results["documents"][i] if results["documents"] else None,
                    "metadata": results["metadatas"][i] if results["metadatas"] else {}
                })
        
        return formatted

    async def delete_section(self, section_id: str) -> bool:
        try:
            self._collection.delete(ids=[section_id])
            logger.info(f"Deleted section {section_id} from vector store")
            return True
        except Exception as e:
            logger.error(f"Failed to delete section {section_id}: {e}")
            return False

    async def delete_by_document(self, document_id: str) -> int:
        results = self._collection.get(
            where={"document_id": document_id},
            include=[]
        )
        
        if results["ids"]:
            self._collection.delete(ids=results["ids"])
            logger.info(f"Deleted {len(results['ids'])} sections for document {document_id}")
            return len(results["ids"])
        
        return 0

    def get_collection_stats(self) -> dict:
        return {
            "name": settings.chroma_collection_name,
            "count": self._collection.count(),
            "initialized": True
        }

    async def reindex_section(
        self,
        section_id: str,
        content: str,
        metadata: dict | None = None
    ) -> str:
        return await self.add_section(section_id, content, metadata)
