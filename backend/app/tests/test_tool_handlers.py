"""Unit tests for AI tool handlers."""
#competely generated
import pytest
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestrator import ToolExecutor, AgentState
from app.ai.tool_schemas import validate_tool_args, SemanticSearchArgs
from app.models.document import Document, DocumentSection
from app.models.suggestion import EditSuggestion, SuggestionStatus


class TestToolSchemaValidation:
    """Test Pydantic validation for tool arguments."""
    
    def test_semantic_search_valid_args(self):
        """Test valid semantic search arguments."""
        args = {"query": "test query", "n_results": 5}
        result = validate_tool_args("semantic_search", args)
        
        assert isinstance(result, SemanticSearchArgs)
        assert result.query == "test query"
        assert result.n_results == 5
    
    def test_semantic_search_invalid_n_results(self):
        """Test semantic search with invalid n_results."""
        args = {"query": "test", "n_results": 100}  # Max is 20
        
        with pytest.raises(ValueError):
            validate_tool_args("semantic_search", args)
    
    def test_semantic_search_empty_query(self):
        """Test semantic search with empty query."""
        args = {"query": "", "n_results": 5}
        
        with pytest.raises(ValueError):
            validate_tool_args("semantic_search", args)
    
    def test_get_section_content_valid_uuid(self):
        """Test get_section_content with valid UUID."""
        section_id = str(uuid4())
        args = {"section_id": section_id}
        
        result = validate_tool_args("get_section_content", args)
        assert result.section_id == section_id
    
    def test_get_section_content_invalid_uuid(self):
        """Test get_section_content with invalid UUID."""
        args = {"section_id": "not-a-uuid"}
        
        with pytest.raises(ValueError):
            validate_tool_args("get_section_content", args)
    
    def test_propose_edit_confidence_bounds(self):
        """Test propose_edit confidence is bounded [0, 1]."""
        section_id = str(uuid4())
        
        # Valid confidence
        args = {
            "section_id": section_id,
            "suggested_text": "new text",
            "reasoning": "because",
            "confidence": 0.75
        }
        result = validate_tool_args("propose_edit", args)
        assert result.confidence == 0.75
        
        # Invalid - too high
        args["confidence"] = 1.5
        with pytest.raises(ValueError):
            validate_tool_args("propose_edit", args)
        
        # Invalid - negative
        args["confidence"] = -0.1
        with pytest.raises(ValueError):
            validate_tool_args("propose_edit", args)
    
    def test_find_dependencies_direction_literal(self):
        """Test find_dependencies validates direction as literal."""
        section_id = str(uuid4())
        
        # Valid directions
        for direction in ["incoming", "outgoing", "both"]:
            args = {"section_id": section_id, "direction": direction}
            result = validate_tool_args("find_dependencies", args)
            assert result.direction == direction
        
        # Invalid direction
        args = {"section_id": section_id, "direction": "invalid"}
        with pytest.raises(ValueError):
            validate_tool_args("find_dependencies", args)
    
    def test_unknown_tool(self):
        """Test validation with unknown tool name."""
        with pytest.raises(ValueError, match="Unknown tool"):
            validate_tool_args("nonexistent_tool", {})


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def agent_state():
    """Create an agent state for testing."""
    return AgentState(
        query_id=uuid4(),
        query_text="Test query"
    )


@pytest.fixture
def tool_executor(mock_db_session, agent_state):
    """Create a tool executor for testing."""
    executor = ToolExecutor(mock_db_session, agent_state)
    
    # Set backing private attributes for mocking
    executor._search_service = AsyncMock()
    executor._dependency_service = AsyncMock()
    
    return executor


class TestSemanticSearchHandler:
    """Test semantic_search tool handler."""
    
    @pytest.mark.asyncio
    async def test_semantic_search_success(self, tool_executor, agent_state):
        """Test successful semantic search."""
        mock_results = [
            {
                "section_id": str(uuid4()),
                "content": "Test content",
                "metadata": {"file_path": "test.md"},
                "score": 0.95
            }
        ]
        
        tool_executor._search_service.search = AsyncMock(return_value=mock_results)
        
        result = await tool_executor._handle_semantic_search({
            "query": "test query",
            "n_results": 10
        })
        
        assert result["count"] == 1
        assert result["query"] == "test query"
        assert len(result["results"]) == 1
        assert "test query" in agent_state.searched_queries
        
        # Verify search was called with correct params
        tool_executor._search_service.search.assert_called_once_with(
            query="test query",
            n_results=10,
            file_path_filter=None,
        )
    
    @pytest.mark.asyncio
    async def test_semantic_search_with_file_filter(self, tool_executor):
        """Test semantic search with file path filter."""
        tool_executor._search_service.search = AsyncMock(return_value=[])
        
        await tool_executor._handle_semantic_search({
            "query": "test",
            "n_results": 5,
            "file_path_filter": "docs/"
        })
        
        tool_executor._search_service.search.assert_called_once_with(
            query="test",
            n_results=5,
            file_path_filter="docs/",
        )


class TestGetSectionContentHandler:
    """Test get_section_content tool handler."""
    
    @pytest.mark.asyncio
    async def test_get_section_success(self, tool_executor, mock_db_session, agent_state):
        """Test successful section retrieval."""
        section_id = uuid4()
        doc_id = uuid4()
        
        # Create mock section with document
        mock_document = Document(
            id=doc_id,
            file_path="test.md",
            title="Test Doc",
            content="Full content",
            checksum="abc123"
        )
        
        mock_section = DocumentSection(
            id=section_id,
            document_id=doc_id,
            section_title="Test Section",
            content="Section content",
            order=0
        )
        mock_section.document = mock_document
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_section
        mock_db_session.execute.return_value = mock_result
        
        result = await tool_executor._handle_get_section({
            "section_id": str(section_id)
        })
        
        assert result["section_id"] == str(section_id)
        assert result["section_title"] == "Test Section"
        assert result["content"] == "Section content"
        assert result["file_path"] == "test.md"
        assert result["order"] == 0
        assert str(section_id) in agent_state.analyzed_sections
    
    @pytest.mark.asyncio
    async def test_get_section_not_found(self, tool_executor, mock_db_session):
        """Test section not found error."""
        section_id = uuid4()
        
        # Mock database query returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        result = await tool_executor._handle_get_section({
            "section_id": str(section_id)
        })
        
        assert "error" in result
        assert str(section_id) in result["error"]


class TestFindDependenciesHandler:
    """Test find_dependencies tool handler."""
    
    @pytest.mark.asyncio
    async def test_find_dependencies_both(self, tool_executor):
        """Test finding dependencies in both directions."""
        section_id = uuid4()
        
        mock_deps = {
            "incoming": [
                {"section_id": str(uuid4()), "dependency_type": "reference"}
            ],
            "outgoing": [
                {"section_id": str(uuid4()), "dependency_type": "link"}
            ]
        }
        
        tool_executor._dependency_service.get_dependencies = AsyncMock(
            return_value=mock_deps
        )
        
        result = await tool_executor._handle_find_dependencies({
            "section_id": str(section_id),
            "direction": "both"
        })
        
        assert result["section_id"] == str(section_id)
        assert result["dependencies"] == mock_deps
        
        tool_executor._dependency_service.get_dependencies.assert_called_once_with(
            section_id=section_id,
            direction="both"
        )


class TestProposeEditHandler:
    """Test propose_edit tool handler."""
    
    @pytest.mark.asyncio
    async def test_propose_edit_success(
        self, 
        tool_executor, 
        mock_db_session,
        agent_state
    ):
        """Test successful edit proposal."""
        section_id = uuid4()
        doc_id = uuid4()
        
        # Create mock section with document
        mock_document = Document(
            id=doc_id,
            file_path="test.md",
            title="Test Doc",
            content="Full content",
            checksum="abc123"
        )
        
        mock_section = DocumentSection(
            id=section_id,
            document_id=doc_id,
            section_title="Test Section",
            content="Original content",
            order=0
        )
        mock_section.document = mock_document
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_section
        mock_db_session.execute.return_value = mock_result
        
        # Mock suggestion creation
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()
        
        result = await tool_executor._handle_propose_edit({
            "section_id": str(section_id),
            "suggested_text": "New content",
            "reasoning": "Update needed",
            "confidence": 0.8
        })
        
        assert result["success"] is True
        assert result["section_id"] == str(section_id)
        assert result["section_title"] == "Test Section"
        assert result["file_path"] == "test.md"
        assert result["confidence"] == 0.8
        assert len(agent_state.proposed_edits) == 1
        
        # Verify suggestion was created
        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_propose_edit_section_not_found(
        self, 
        tool_executor, 
        mock_db_session
    ):
        """Test propose_edit with non-existent section."""
        section_id = uuid4()
        
        # Mock database query returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        result = await tool_executor._handle_propose_edit({
            "section_id": str(section_id),
            "suggested_text": "New content",
            "reasoning": "Update needed",
            "confidence": 0.8
        })
        
        assert "error" in result
        assert str(section_id) in result["error"]
    
    @pytest.mark.asyncio
    async def test_propose_edit_confidence_clamping(
        self,
        tool_executor,
        mock_db_session
    ):
        """Test confidence is clamped to [0, 1] range."""
        section_id = uuid4()
        
        mock_section = DocumentSection(
            id=section_id,
            document_id=uuid4(),
            section_title="Test",
            content="Content",
            order=0
        )
        mock_section.document = Document(
            id=uuid4(),
            file_path="test.md",
            title="Test",
            content="Content",
            checksum="abc"
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_section
        mock_db_session.execute.return_value = mock_result
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()
        
        # Test confidence > 1 is clamped to 1
        result = await tool_executor._handle_propose_edit({
            "section_id": str(section_id),
            "suggested_text": "New",
            "reasoning": "Because",
            "confidence": 1.5
        })
        
        assert result["confidence"] == 1.0


class TestGetDocumentStructureHandler:
    """Test get_document_structure tool handler."""
    
    @pytest.mark.asyncio
    async def test_get_document_structure_success(
        self,
        tool_executor,
        mock_db_session
    ):
        """Test successful document structure retrieval."""
        doc_id = uuid4()
        
        # Create mock document with sections
        mock_document = Document(
            id=doc_id,
            file_path="test.md",
            title="Test Document",
            content="Full content",
            checksum="abc123"
        )
        
        mock_sections = [
            DocumentSection(
                id=uuid4(),
                document_id=doc_id,
                section_title="Introduction",
                content="Intro content",
                order=0
            ),
            DocumentSection(
                id=uuid4(),
                document_id=doc_id,
                section_title="Conclusion",
                content="Conclusion content",
                order=1
            )
        ]
        mock_document.sections = mock_sections
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db_session.execute.return_value = mock_result
        
        result = await tool_executor._handle_get_document_structure({
            "document_id": str(doc_id)
        })
        
        assert result["document_id"] == str(doc_id)
        assert result["file_path"] == "test.md"
        assert result["title"] == "Test Document"
        assert len(result["sections"]) == 2
        assert result["sections"][0]["title"] == "Introduction"
        assert result["sections"][1]["title"] == "Conclusion"
    
    @pytest.mark.asyncio
    async def test_get_document_structure_not_found(
        self,
        tool_executor,
        mock_db_session
    ):
        """Test document not found error."""
        doc_id = uuid4()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        result = await tool_executor._handle_get_document_structure({
            "document_id": str(doc_id)
        })
        
        assert "error" in result
        assert str(doc_id) in result["error"]


class TestSearchByFilePathHandler:
    """Test search_by_file_path tool handler."""
    
    @pytest.mark.asyncio
    async def test_search_by_file_path_success(self, tool_executor):
        """Test successful file path search."""
        mock_results = [
            {
                "section_id": str(uuid4()),
                "content": "Content",
                "metadata": {"file_path": "agents/handoffs.md"},
                "score": 0.9
            }
        ]
        
        tool_executor._search_service.search_by_file_path = AsyncMock(
            return_value=mock_results
        )
        
        result = await tool_executor._handle_search_by_file_path({
            "path_pattern": "agents/"
        })
        
        assert result["count"] == 1
        assert result["pattern"] == "agents/"
        assert len(result["results"]) == 1
        
        tool_executor._search_service.search_by_file_path.assert_called_once_with(
            path_pattern="agents/",
            n_results=20,
        )


class TestToolExecutor:
    """Test ToolExecutor.execute() method."""
    
    @pytest.mark.asyncio
    async def test_execute_with_validation(self, tool_executor):
        """Test execute validates arguments before calling handler."""
        tool_executor._search_service.search = AsyncMock(return_value=[])
        
        # Valid args
        result = await tool_executor.execute("semantic_search", {
            "query": "test",
            "n_results": 5
        })
        
        assert "error" not in result
        
        # Invalid args - should return validation error
        result = await tool_executor.execute("semantic_search", {
            "query": "test",
            "n_results": 100  # Exceeds max of 20
        })
        
        assert "error" in result
        assert "Validation error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, tool_executor):
        """Test execute with unknown tool name."""
        result = await tool_executor.execute("unknown_tool", {})
        
        assert "error" in result
        assert "Unknown tool" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execute_handler_exception(self, tool_executor, mock_db_session):
        """Test execute handles handler exceptions."""
        # Make handler raise exception
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.side_effect = Exception("DB error")
        mock_db_session.execute.return_value = mock_result
        
        result = await tool_executor.execute("get_section_content", {
            "section_id": str(uuid4())
        })
        
        assert "error" in result
        assert "DB error" in result["error"]

