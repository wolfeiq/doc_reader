from typing import Any, TypedDict, NotRequired


class ToolFunction(TypedDict):
    name: str
    description: str
    parameters: dict[str, Any]


class Tool(TypedDict):
    type: str
    function: ToolFunction


TOOLS: list[Tool] = [
    {
        "type": "function",
        "function": {
            "name": "semantic_search",
            "description": "Search documentation for sections semantically related to a query. Use this to find sections that might need updating based on the user's change description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query describing what to look for"
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of results to return (default: 10, max: 20)",
                        "default": 10
                    },
                    "file_path_filter": {
                        "type": "string",
                        "description": "Optional: filter results to a specific file path pattern"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_section_content",
            "description": "Get the full content of a specific documentation section by its ID. Use this after semantic search to get complete context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "section_id": {
                        "type": "string",
                        "description": "The UUID of the section to retrieve"
                    }
                },
                "required": ["section_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_dependencies",
            "description": "Find sections that reference or depend on a given section. Use this to identify sections that might also need updates due to dependencies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "section_id": {
                        "type": "string",
                        "description": "The UUID of the section to find dependencies for"
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["incoming", "outgoing", "both"],
                        "description": "Direction of dependencies: 'incoming' (sections that reference this one), 'outgoing' (sections this one references), or 'both'",
                        "default": "both"
                    }
                },
                "required": ["section_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "propose_edit",
            "description": "Propose an edit to a documentation section. Call this when you've identified a section that needs updating.",
            "parameters": {
                "type": "object",
                "properties": {
                    "section_id": {
                        "type": "string",
                        "description": "The UUID of the section to edit"
                    },
                    "suggested_text": {
                        "type": "string",
                        "description": "The proposed new content for this section"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Explanation of why this edit is needed and what changed"
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence score from 0.0 to 1.0 indicating how certain you are this edit is correct",
                        "minimum": 0,
                        "maximum": 1
                    }
                },
                "required": ["section_id", "suggested_text", "reasoning", "confidence"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_document_structure",
            "description": "Get the structure of a document showing all its sections. Use this to understand the organization of a document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "The UUID of the document"
                    }
                },
                "required": ["document_id"]
            }
        }
    },
    {
        "type": "function", 
        "function": {
            "name": "search_by_file_path",
            "description": "List all sections in documents matching a file path pattern. Use this when you know which file(s) to look at.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path_pattern": {
                        "type": "string",
                        "description": "File path or pattern to match (e.g., 'agents/', 'handoffs.md')"
                    }
                },
                "required": ["path_pattern"]
            }
        }
    }
]


def get_tool_names() -> list[str]:
    return [tool["function"]["name"] for tool in TOOLS]


def get_tool_by_name(name: str) -> Tool | None:
    for tool in TOOLS:
        if tool["function"]["name"] == name:
            return tool
    return None