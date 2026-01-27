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