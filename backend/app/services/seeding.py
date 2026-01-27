"""
Seeding Service - Database Population & Reset Utilities
========================================================

This module provides utilities for populating the database with
documentation content and resetting state. Used for:

1. Initial Setup - Populate empty database with markdown docs
2. Testing - Reset to known state between tests
3. Development - Quickly reload content after changes
4. Deployment - Seed production database via admin endpoint

Seeding Process:
----------------
1. Find all .md files in the specified directory
2. For each file:
   a. Check if document already exists (by file_path)
   b. If exists, compare checksum - update only if changed
   c. If new, create document with sections and embeddings
3. Build dependency graph between sections

The checksum comparison prevents unnecessary reprocessing and
avoids regenerating expensive embeddings for unchanged content.

Clear Operations:
-----------------
clear_database() - Removes all data from PostgreSQL tables
clear_vectors() - Removes all embeddings from ChromaDB

IMPORTANT: These operations are destructive and irreversible.
The admin endpoint requires a secret to prevent accidental calls.

Production Considerations:
--------------------------
- Add progress reporting for large documentation sets
- Consider parallel processing for faster seeding
- Add dry-run mode to preview changes
- Implement incremental sync (only changed files)
"""

import logging
from pathlib import Path

from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models.document_base import Document
from app.models.document import DocumentSection

from app.models.section_dependency import SectionDependency
from app.models.history import EditHistory
from app.models.query import Query
from app.models.suggestion import EditSuggestion
from app.services.document_service import DocumentService
from app.services.search_service import SearchService
from app.utils.files import find_markdown_files

logger = logging.getLogger(__name__)


async def seed_documents(base_path: Path) -> None:
    """
    Seed the database with markdown documentation files.

    Recursively finds all .md files under base_path and creates/updates
    documents in the database. Uses checksum comparison to avoid
    reprocessing unchanged files.

    Process per file:
    1. Read file content
    2. Check if document exists by file_path
    3. If exists: compare checksum, update only if changed
    4. If new: create document, parse sections, generate embeddings

    Args:
        base_path: Root directory containing markdown files.
                   File paths are stored relative to this directory.

    Side Effects:
        - Creates/updates Document records in PostgreSQL
        - Creates/updates DocumentSection records
        - Generates vector embeddings in ChromaDB
        - Builds section dependency graph

    Example:
        await seed_documents(Path("data/openai-agents-sdk"))
        # Creates documents like "agents.md", "tools/overview.md", etc.

    Cost Considerations:
        - OpenAI embedding API calls (~$0.00002 per 1K tokens)
        - A 500-token section costs ~$0.00001 to embed
        - 1000 sections ≈ $0.01 in API costs
    """
    md_files = find_markdown_files(base_path)

    created = updated = skipped = errors = 0

    async with AsyncSessionLocal() as db:
        service = DocumentService(db)

        for file_path in md_files:
            try:
                content = file_path.read_text(encoding="utf-8").strip()
                if not content:
                    skipped += 1
                    continue

                relative_path = str(file_path.relative_to(base_path))
                existing = await service.get_document_by_path(relative_path)

                if existing:
                    checksum = service.calculate_checksum(content)
                    if checksum != existing.checksum:
                        await service.update_document(relative_path, content)
                        updated += 1
                else:
                    await service.create_document(
                        file_path=relative_path,
                        content=content,
                        generate_embeddings=True,
                    )
                    created += 1

                await db.commit()

            except Exception:
                errors += 1
                await db.rollback()
                logger.exception("Failed to process %s", file_path)

    logger.info(
        "Seeding complete | created=%d updated=%d skipped=%d errors=%d",
        created,
        updated,
        skipped,
        errors,
    )


async def clear_database() -> None:
    """
    Delete all data from PostgreSQL tables.

    DESTRUCTIVE OPERATION - Removes ALL:
    - Edit history records
    - Edit suggestions
    - User queries
    - Section dependencies
    - Document sections
    - Documents

    Deletion order matters due to foreign key constraints:
    1. EditHistory (references suggestions, sections, documents)
    2. EditSuggestion (references queries, sections)
    3. Query (standalone)
    4. SectionDependency (references sections)
    5. DocumentSection (references documents)
    6. Document (base table)

    Use Case:
        Called before re-seeding to ensure clean state.
        Also used in tests for isolation between test cases.

    WARNING:
        This does NOT clear ChromaDB vectors - call clear_vectors()
        separately if you need to reset embeddings too.
    """
    async with AsyncSessionLocal() as db:
        await db.execute(EditHistory.__table__.delete())
        await db.execute(EditSuggestion.__table__.delete())
        await db.execute(Query.__table__.delete())
        await db.execute(SectionDependency.__table__.delete())
        await db.execute(DocumentSection.__table__.delete())
        await db.execute(Document.__table__.delete())
        await db.commit()


async def clear_vectors() -> None:
    """
    Delete all vector embeddings from ChromaDB.

    DESTRUCTIVE OPERATION - Removes all document embeddings.
    The collection itself is preserved but emptied.

    This is separate from clear_database() because:
    1. Different storage backends (PostgreSQL vs ChromaDB)
    2. May want to clear one without the other
    3. ChromaDB operations can fail independently

    Error Handling:
        Failures are logged as warnings but don't raise.
        This allows seeding to continue even if ChromaDB is unavailable.
    """
    search = SearchService()
    try:
        search.clear_collection()
    except Exception:
        logger.warning("Failed to clear vector store", exc_info=True)


async def show_stats() -> None:
    """
    Log current database statistics.

    Useful for verifying seeding success or debugging.
    Queries both PostgreSQL and ChromaDB for counts.

    Logs:
        - Documents: Total document count
        - Sections: Total section count (typically 5-15x documents)
        - Vectors: Embedding count in ChromaDB (should match sections)

    Example Output:
        "Documents: 30 | Sections: 282 | Vectors: 259"

    Note:
        Vector count may be less than section count if some
        sections were empty or embedding generation failed.
    """
    async with AsyncSessionLocal() as db:
        documents = await db.scalar(select(func.count(Document.id)))
        sections = await db.scalar(select(func.count(DocumentSection.id)))

    vectors = SearchService().get_collection_stats().get("count", 0)

    logger.info(
        "Documents: %d | Sections: %d | Vectors: %d",
        documents,
        sections,
        vectors,
    )
