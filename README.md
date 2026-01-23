# doc_reader

Phase 0 ✅

- Project structure created
- Docker Compose for PostgreSQL + ChromaDB
- Environment configuration
- README and TRADEOFFS docs

Phase 1 ✅

- SQLAlchemy models (Document, Section, Query, Suggestion, History, Dependencies)
- Pydantic schemas for all models
- Database session management
- Document service with section parsing
- History service

Phase 2 ✅

- ChromaDB search service with OpenAI embeddings
- AI orchestrator with streaming
- SSE endpoints for real-time progress
- All API routes (documents, queries, suggestions, history)
- Optional Celery Tasks for Background Job Orchestration - Query Processing and Document Reindexing Tasks

ToDo:

- Phase 3-4: Frontend (Next.js setup, components, streaming UI)
- Phase 5-7: Advanced features (dependency visualization, preview mode)