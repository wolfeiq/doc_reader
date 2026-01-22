import logging
from typing import Optional
from uuid import UUID
import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class SearchService:

    def __init__(self):
        self._client: Optional[chromadb.Client] = None
        self._collection: Optional[chromadb.Collection] = None
        self._openai: Optional[AsyncOpenAI] = None

    async def initialize(self) -> None:
        try: #railway
            if settings.environment == "production":
                self._client = chromadb.HttpClient(
                    host=settings.chroma_host,
                    port=settings.chroma_port,
                )
            else: #local
                self._client = chromadb.PersistentClient(
                    path="./chroma_data",
                    settings=ChromaSettings(
                        anonymized_telemetry=False,
                        allow_reset=True,
                    ),
                )

            self._collection = self._client.get_or_create_collection(
                name=settings.chroma_collection_name,
                metadata={"hnsw:space": "cosine"},
            )

            self._openai = AsyncOpenAI(api_key=settings.openai_api_key)

            logger.info(
                f"ChromaDB initialized. Collection '{settings.chroma_collection_name}' "
                f"has {self._collection.count()} documents."
            )

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise

    async def close(self) -> None:
        pass

    async def _get_embedding(self, text: str) -> list[float]:
        response = await self._openai.embeddings.create(
            model=settings.openai_embedding_model,
            input=text,
        )
        return response.data[0].embedding

    async def add_section(
        self,
        section_id: UUID,
        content: str,
        metadata: dict,
    ) -> str:
        if not self._collection:
            raise RuntimeError("SearchService not initialized")

        embedding = await self._get_embedding(content)
        doc_id = str(section_id)

        self._collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata],
        )

        logger.debug(f"Added section {section_id} to ChromaDB")
        return doc_id

    async def update_section(
        self,
        section_id: UUID,
        content: str,
        metadata: dict,
    ) -> str:
        return await self.add_section(section_id, content, metadata)

    async def delete_section(self, section_id: UUID) -> None:
        if not self._collection:
            raise RuntimeError("SearchService not initialized")

        doc_id = str(section_id)
        try:
            self._collection.delete(ids=[doc_id])
            logger.debug(f"Deleted section {section_id} from ChromaDB")
        except Exception as e:
            logger.warning(f"Failed to delete section {section_id}: {e}")

    async def search(
        self,
        query: str,
        n_results: int = 10,
        filter_metadata: Optional[dict] = None,
    ) -> list[dict]:
        if not self._collection:
            raise RuntimeError("SearchService not initialized")

        embedding = await self._get_embedding(query)

        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=filter_metadata,
            include=["documents", "metadatas", "distances"],
        )

        sections = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                sections.append({
                    "section_id": UUID(doc_id),
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                    "score": 1 - (results["distances"][0][i] if results["distances"] else 0),
                })

        return sections

    async def search_by_keywords(
        self,
        keywords: list[str],
        n_results: int = 10,
    ) -> list[dict]:
        query = " ".join(keywords)
        return await self.search(query, n_results)

    async def get_collection_stats(self) -> dict:
        if not self._collection:
            return {"count": 0, "initialized": False}

        return {
            "count": self._collection.count(),
            "initialized": True,
            "name": settings.chroma_collection_name,
        }

    async def clear_collection(self) -> None:
        if not self._collection or not self._client:
            return

        self._client.delete_collection(settings.chroma_collection_name)
        self._collection = self._client.create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB collection cleared")



search_service = SearchService()
