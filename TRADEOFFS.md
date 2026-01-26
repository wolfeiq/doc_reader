# Tradeoffs & Design Decisions

This document tracks decisions made for speed vs. what would be done in production.

## Implemented (Production-Ready)

### Database
- ✅ **PostgreSQL with async SQLAlchemy** - Production-grade database with proper async support
- ✅ **Proper migrations ready** - Alembic configured for schema migrations
- ✅ **UUID primary keys** - Better for distributed systems
- ✅ **Timestamps on all models** - created_at, updated_at with timezone support

### Search
- ✅ **ChromaDB for vector search** - Persistent storage, production-capable
- ✅ **OpenAI embeddings** - Using text-embedding-3-small for cost efficiency
- ✅ **Semantic search** - Finding relevant sections based on meaning, not just keywords

### API
- ✅ **SSE streaming** - Real-time progress updates with Celery
- ✅ **Proper error handling** - HTTP status codes and error messages
- ✅ **Pagination** - For list endpoints
- ✅ **Type validation** - Pydantic schemas for all endpoints

### AI
- ✅ **Structured output** - JSON mode for reliable parsing
- ✅ **Confidence scores** - Filter low-confidence suggestions
- ✅ **Multi-step analysis** - Analyze query → Search → Generate suggestions

## Tradeoffs Made for Speed

### Authentication & Security
- ❌ **No authentication** - Would add JWT/OAuth in production
- ❌ **No rate limiting** - Would add Redis-based rate limiting
- ❌ **No API keys** - Would require API keys for access
- **Production approach**: Auth0/Clerk for auth, Redis for rate limiting

### Database
- ❌ **No connection pooling config** - Using NullPool for simplicity
- **Production approach**: Configure pgBouncer or SQLAlchemy pool settings

### Caching
- ❌ **No response caching** - Every request hits the database
- **Production approach**: Redis caching for documents, search results

### Search
- ❌ **No re-ranking** - Taking top results as-is
- ❌ **No hybrid search** - Only semantic, no keyword fallback
- **Production approach**: Add BM25 hybrid search, LLM re-ranking

### AI
- ❌ **Simple two-stage pipeline** - Could be more agentic
- ❌ **No retry logic for OpenAI** - Single attempt
- ❌ **No token limit handling** - Might fail on very long sections
- **Production approach**: 
  - Full agentic loop with tool calling
  - Tenacity for retries with exponential backoff
  - Token counting and chunking for long content

### Dependency Analysis
- ❌ **Basic implementation** - Not fully connected
- **Production approach**: Build dependency graph on document ingest, use for cascading suggestions


### Monitoring
- ❌ **Basic logging only** - No metrics or tracing
- **Production approach**: 
  - Prometheus metrics
  - Sentry for error tracking
  - OpenTelemetry for distributed tracing

### Frontend
- ❌ **Error boundaries basic** - Minimal error handling
- ❌ **No optimistic updates** - Waiting for server response
- **Production approach**: Full optimistic updates with rollback

## Future Improvements

### High Priority
1. **Full agentic RAG** - Multi-turn tool calling for better analysis
2. **Dependency graph** - Automatic detection of cross-references
3. **Undo/redo** - Revert changes from history
4. **Batch apply** - Apply multiple suggestions at once
5. **Export as PR** - Generate git diff or GitHub PR

### Medium Priority
1. **Keyboard shortcuts** - j/k navigate, a/r accept/reject
2. **Dark mode** - User preference
3. **Document versioning** - Track document versions over time
4. **Conflict detection** - Warn if section changed since suggestion generated
5. **Custom prompts** - Let users customize AI behavior
