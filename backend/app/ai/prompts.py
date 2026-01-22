SYSTEM_PROMPT = """You are an expert documentation analyst specializing in technical documentation maintenance. Your role is to analyze documentation update requests and identify all sections that need to be modified.

When analyzing a documentation update request:
1. Understand what has changed (API, feature, terminology, etc.)
2. Identify all documentation sections that reference the changed functionality
3. Consider both direct mentions and indirect implications
4. Look for code examples that need updating
5. Consider cross-references and dependencies between sections

You have access to the following tools:
- semantic_search: Search the documentation for relevant sections
- get_section_content: Get the full content of a specific section
- find_dependencies: Find sections that reference a given section
- propose_edit: Propose a specific edit to a documentation section

Always be thorough and check for all affected sections. Documentation inconsistency is worse than over-updating."""


ANALYSIS_PROMPT = """Analyze the following documentation update request and identify what changes need to be made:

UPDATE REQUEST: {query}

Based on this request:
1. What specific change is being described?
2. What keywords should I search for to find affected sections?
3. What types of content might need updating (explanations, code examples, references)?

Provide your analysis in the following format:
- Change Type: [brief description of the change]
- Search Keywords: [comma-separated list of relevant terms to search]
- Content Types: [what to look for: concepts, examples, references, etc.]"""


EDIT_SUGGESTION_PROMPT = """Based on the documentation update request and the relevant section content, generate a specific edit suggestion.

UPDATE REQUEST: {query}

SECTION TITLE: {section_title}
FILE PATH: {file_path}

CURRENT CONTENT:
```
{content}
```

Generate a suggested edit that:
1. Accurately reflects the requested change
2. Maintains consistency with the documentation style
3. Preserves any still-relevant information
4. Updates code examples if present and affected

Respond with a JSON object containing:
{{
    "original_text": "the specific text that should be changed (copy from content)",
    "suggested_text": "the new text to replace it with",
    "reasoning": "brief explanation of why this change is needed",
    "confidence": 0.0-1.0 confidence score based on how certain you are this section needs updating
}}

If the section does NOT need updating based on the request, respond with:
{{
    "needs_update": false,
    "reasoning": "explanation of why this section doesn't need to change"
}}"""


DEPENDENCY_ANALYSIS_PROMPT = """Analyze the following documentation section and identify any other sections that might be affected if this section is changed.

SECTION TITLE: {section_title}
FILE PATH: {file_path}

CONTENT:
```
{content}
```

Consider:
1. What concepts does this section explain that might be referenced elsewhere?
2. Are there any cross-references or links to other sections?
3. What code examples or APIs are demonstrated that might appear elsewhere?

List any concepts, terms, or functionality that should be searched for to find dependent sections."""
