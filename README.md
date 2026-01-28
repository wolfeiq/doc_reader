# doc_reader

This is an AI agent platform designed to analyze technical documentation and propose intelligent edits, using a simple "Reasoning & Action" (ReAct) loop.

## What happens

* **Autonomous AI Agent**: Uses a ReAct loop to perform multi-step analysis (Search -> Read -> Propose).
* **Real-time Streaming (SSE)**: Watch the AI's "thought process" live as it executes tools and finds sections.
* **Intelligent Diffing**: View original vs. suggested text in split or unified modes.
* **Vector Search**: Powered by ChromaDB for semantic retrieval of relevant document sections.
* **Asynchronous Processing**: Celery & Redis handle long-running AI tasks without blocking the UI.

## The Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.12)
- **Database**: PostgreSQL (SQLAlchemy + AsyncPG)
- **Task Queue**: Celery + Redis
- **Vector Store**: ChromaDB
- **LLM**: OpenAI GPT-4o (via Tool Calling)

### Frontend
- **Framework**: Next.js 14 (App Router)
- **Server State**: TanStack React Query (v5)
- **Client State**: Zustand (with Persist middleware)
- **Styling**: Tailwind CSS

---

## Architecture Flow

1.  **Query Input**: User submits a natural language request (e.g., "Standardize the Runner nomenclature").
2.  **Task Delegation**: FastAPI triggers a Celery worker.
3.  **Agent Loop**:
    * `semantic_search`: Finds relevant sections in ChromaDB.
    * `get_section_content`: Reads the full text of candidate sections.
    * `propose_edit`: Generates a suggestion with reasoning and confidence.
4.  **Live Updates**: The worker publishes events to Redis; the frontend streams these via Server-Sent Events (SSE).
5.  **Human-in-the-loop**: User reviews, edits, or accepts the suggestions.

Simple SSE without background tasks also an alternative implemented in the code, as well as an option without streaming at all with just Celery.

---

## AI Architecture: Tool Calling vs Prompt Templates

This project uses **OpenAI Function Calling (Tools)** rather than traditional prompt templates. Here's why and how they differ:

### The Old Approach: Prompt Templates

Traditional LLM applications use prompt templates to structure AI responses:

```python
EDIT_SUGGESTION_PROMPT = """
UPDATE REQUEST: {query}
SECTION TITLE: {section_title}
CURRENT CONTENT:
{content}

Generate a suggested edit as JSON:
{{
    "original_text": "text to change",
    "suggested_text": "new text",
    "reasoning": "why this change",
    "confidence": 0.0-1.0
}}
"""

# For each section, make a separate API call
for section in sections:
    response = openai.chat.completions.create(
        messages=[{"role": "user", "content": EDIT_SUGGESTION_PROMPT.format(...)}]
    )
    result = json.loads(response)  # Can fail if AI doesn't follow format
```

**Pros:**
- Predictable, controlled output format
- Easy to understand and debug
- Works with any LLM (no function calling required)

**Cons:**
- AI can return malformed JSON (parsing errors)
- One API call per section (slow, expensive)
- No context between sections
- Rigid - AI can't decide to skip irrelevant sections

### The New Approach: Tool Calling (ReAct Agent)

This project uses OpenAI's function calling with a ReAct-style agent loop:

```python
# Define tools with JSON schemas - OpenAI GUARANTEES valid responses
TOOLS = [{
    "type": "function",
    "function": {
        "name": "propose_edit",
        "parameters": {
            "properties": {
                "section_id": {"type": "string"},
                "suggested_text": {"type": "string"},  # AI writes edit here
                "reasoning": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1}
            },
            "required": ["section_id", "suggested_text", "reasoning", "confidence"]
        }
    }
}]

# Single conversation - AI decides when to call which tool
response = openai.chat.completions.create(
    messages=conversation_history,
    tools=TOOLS,
    tool_choice="auto"  # AI chooses which tool to call
)

# OpenAI guarantees tool_call.arguments is valid JSON matching schema
for tool_call in response.tool_calls:
    args = json.loads(tool_call.function.arguments)  # Always valid!
```

**Pros:**
- Guaranteed valid JSON (schema-enforced by OpenAI)
- AI maintains context across multiple tool calls
- AI can search, read, and decide autonomously
- Fewer API calls (one conversation, multiple actions)
- AI can skip irrelevant sections intelligently

**Cons:**
- Less predictable (AI has more autonomy)
- Requires OpenAI function calling support
- Harder to debug (multi-turn conversation)

### Comparison Table

| Aspect | Prompt Templates | Tool Calling (Current) |
|--------|------------------|------------------------|
| **Format Safety** | Can fail JSON parsing | Schema guarantees valid JSON |
| **API Calls** | One per section | One conversation, many actions |
| **Context** | Isolated per section | Full conversation history |
| **AI Autonomy** | Low (follows template) | High (decides what to do) |
| **Debugging** | Easy (see each prompt) | Harder (multi-turn state) |
| **Cost** | Higher (many calls) | Lower (fewer calls) |
| **Flexibility** | Rigid format | AI adapts to query |

### Key Files

- `backend/app/ai/tools.py` - Tool definitions (JSON schemas)
- `backend/app/ai/orchestrator.py` - Agent loop implementation
- `backend/app/ai/tool_executor.py` - Tool execution handlers
- `backend/app/ai/prompts.py` - System prompt (only `SYSTEM_PROMPT` is used)

---

## Tool Design: Current Architecture & Trade-offs

The AI agent has access to 6 tools. A key design decision is keeping `semantic_search` and `get_section_content` as separate tools rather than combining them.

### Available Tools

| Tool | Purpose | Returns |
|------|---------|---------|
| `semantic_search` | Find relevant sections by query | Section IDs, titles, 200-char previews, scores |
| `get_section_content` | Read full content of a section | Complete section text |
| `find_dependencies` | Find cross-references | Incoming/outgoing section links |
| `propose_edit` | Create an edit suggestion | Suggestion ID, confirmation |
| `get_document_structure` | List sections in a document | Section titles and order |
| `search_by_file_path` | Find sections by file path | Sections matching path pattern |

### Current Flow: Separate Tools

```
AI: semantic_search(query="authentication")
    → Returns 10 results with 200-char previews (~2K tokens)

AI: get_section_content(section_id="abc")   # Reads only sections it needs
AI: get_section_content(section_id="def")
AI: get_section_content(section_id="ghi")
    → 3 full sections (~3K tokens)

Total: ~5K tokens
```

### Alternative: Combined Tool

```
AI: semantic_search(query="authentication", include_full_content=true)
    → Returns 10 results with FULL content (~10K+ tokens)

Total: ~10K+ tokens (but fewer API round trips)
```

### Trade-off Analysis

| Aspect | Separate Tools (Current) | Combined Tool |
|--------|--------------------------|---------------|
| **API Round Trips** | Multiple (1 search + N reads) | Single |
| **Token Usage** | Lower (selective reading) | Higher (all content returned) |
| **Latency** | Higher (multiple calls) | Lower (one call) |
| **AI Control** | AI chooses what to read deeply | AI gets everything upfront |
| **Cost** | Lower input tokens | Higher input tokens |
| **Flexibility** | AI can skip irrelevant results | Must process all results |

### Why We Chose Separate Tools

1. **Token Efficiency**: Search often returns 10+ results, but AI typically only needs 2-3. Returning full content for all would waste tokens.

2. **AI Autonomy**: AI can skim previews and decide which sections deserve deep reading. This mimics how humans work.

3. **Iterative Refinement**: AI can search, read one section, realize it needs different results, and search again with refined query.

### Potential Improvements

| Option | Description | Trade-off |
|--------|-------------|-----------|
| **Longer Previews** | Increase preview from 200 to 1000 chars | More context without full content |
| **Batch Read Tool** | `get_sections_batch(ids=["a","b","c"])` | One call for multiple sections |
| **Optional Full Content** | `semantic_search(..., include_content=true)` | Flexibility when needed |
| **Smart Caching** | Cache recently fetched sections | Reduce redundant reads |

### Limitation: Content-Only Editing

The current tools only support **content modification**, not **structural changes**. The AI can read document structure but cannot modify it.

#### What Each Tool Can Do

| Tool | Can Read | Can Modify |
|------|----------|------------|
| `semantic_search` | Section content, metadata | Nothing |
| `get_section_content` | Full section text | Nothing |
| `get_document_structure` | Section titles, order | Nothing |
| `search_by_file_path` | Sections in file | Nothing |
| `find_dependencies` | Cross-references | Nothing |
| `propose_edit` | Section content | **Only text content** |

#### What the AI Can vs Cannot Do

| User Request | Supported? | Reason |
|--------------|------------|--------|
| "Update the authentication docs" | ✅ Yes | Edits content via `propose_edit` |
| "Fix typos in section X" | ✅ Yes | Edits content |
| "Reorder sections in agents.md" | ❌ No | No tool to change `order` field |
| "Move section A before section B" | ❌ No | No tool to modify structure |
| "Rename 'Setup' to 'Installation'" | ❌ No | No tool to change `section_title` |
| "Delete the deprecated section" | ❌ No | No delete tool |
| "Add a new FAQ section" | ❌ No | No create tool |
| "Split this section into two" | ❌ No | No structural modification tools |

#### Why This Limitation Exists

The `propose_edit` tool schema only accepts content changes:

```python
"parameters": {
    "properties": {
        "section_id": {"type": "string"},
        "suggested_text": {"type": "string"},  # ← Only content, not structure
        "reasoning": {"type": "string"},
        "confidence": {"type": "number"}
    }
}
```

Missing parameters that would enable structural edits:
- `new_order` - Change section position
- `new_title` - Rename section header
- `move_to_document` - Move section to different file
- `delete` - Remove section entirely
- `create_after` - Insert new section

#### Future: Structural Editing Tools

To support structural changes, additional tools would be needed:

```python
# Reorder sections
{"name": "reorder_sections", "parameters": {"document_id": "...", "section_order": ["id1", "id2", ...]}}

# Rename section
{"name": "rename_section", "parameters": {"section_id": "...", "new_title": "..."}}

# Delete section
{"name": "delete_section", "parameters": {"section_id": "...", "reasoning": "..."}}

# Create section
{"name": "create_section", "parameters": {"document_id": "...", "title": "...", "content": "...", "after_section_id": "..."}}
```

---

## Model Selection: GPT-4o and Beyond

### Why GPT-4o?

This project uses **GPT-4o** (`gpt-4o`) as the default model for the AI agent. Here's why:

| Requirement | Why GPT-4o Fits |
|-------------|-----------------|
| **Tool Calling** | Excellent function calling support with reliable JSON schema adherence |
| **Context Window** | 128K tokens - handles long documentation + conversation history |
| **Reasoning** | Strong multi-step reasoning for ReAct agent loops |
| **Speed** | Faster than GPT-4 Turbo while maintaining quality |
| **Code Understanding** | Accurately interprets technical documentation and code examples |

**Cost Consideration:**
- Input: $2.50 per 1M tokens
- Output: $10.00 per 1M tokens
- A typical query (5-10 iterations) costs ~$0.05-0.15

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

- Phase 3-4: Frontend (Next.js setup, components, streaming UI) ✅
- Phase 5-7: Advanced features (dependency visualization, preview mode) ✅
- Preview Mode: YES, Dependency Vis: NO
- Integration Tests, TypeSafety Needs to be Redone, Deployment


![Screen](assets/screenshot.png)