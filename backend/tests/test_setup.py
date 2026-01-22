import asyncio
import sys
from pathlib import Path

# Add the backend directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_config():
    """Test configuration loads correctly."""
    print("\n" + "=" * 50)
    print("TEST: Configuration")
    print("=" * 50)
    
    try:
        from app.config import settings
        
        print(f"✓ App name: {settings.app_name}")
        print(f"✓ Environment: {settings.environment}")
        print(f"✓ Database URL: {settings.database_url[:50]}...")
        print(f"✓ OpenAI model: {settings.openai_model}")
        print(f"✓ ChromaDB: {settings.chroma_host}:{settings.chroma_port}")
        
        if not settings.openai_api_key:
            print("⚠ WARNING: OPENAI_API_KEY is not set!")
        else:
            print(f"✓ OpenAI API key: {settings.openai_api_key[:10]}...")
        
        return True
    except Exception as e:
        print(f"✗ Configuration failed: {e}")
        return False


async def test_models():
    """Test that all models can be imported."""
    print("\n" + "=" * 50)
    print("TEST: Database Models")
    print("=" * 50)
    
    try:
        from app.models import (
            Document,
            DocumentSection,
            SectionDependency,
            Query,
            QueryStatus,
            EditSuggestion,
            SuggestionStatus,
            EditHistory,
            UserAction,
        )
        
        print("✓ Document model imported")
        print("✓ DocumentSection model imported")
        print("✓ SectionDependency model imported")
        print("✓ Query model imported")
        print("✓ QueryStatus enum imported")
        print("✓ EditSuggestion model imported")
        print("✓ SuggestionStatus enum imported")
        print("✓ EditHistory model imported")
        print("✓ UserAction enum imported")
        
        # Test enum values
        assert QueryStatus.PENDING.value == "pending"
        assert SuggestionStatus.ACCEPTED.value == "accepted"
        assert UserAction.EDITED.value == "edited"
        print("✓ Enum values correct")
        
        return True
    except Exception as e:
        print(f"✗ Models import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_schemas():
    """Test that all Pydantic schemas work."""
    print("\n" + "=" * 50)
    print("TEST: Pydantic Schemas")
    print("=" * 50)
    
    try:
        from app.schemas import (
            DocumentCreate,
            DocumentResponse,
            QueryCreate,
            QueryResponse,
            SuggestionCreate,
            SuggestionResponse,
            HistoryCreate,
            HistoryResponse,
        )
        
        # Test DocumentCreate
        doc = DocumentCreate(
            file_path="test/doc.md",
            content="# Test\n\nThis is a test document.",
        )
        assert doc.file_path == "test/doc.md"
        print("✓ DocumentCreate schema works")
        
        # Test QueryCreate
        query = QueryCreate(query_text="Update the API references")
        assert query.query_text == "Update the API references"
        print("✓ QueryCreate schema works")
        
        # Test validation
        try:
            QueryCreate(query_text="")  # Should fail - min_length=1
            print("✗ QueryCreate should reject empty string")
            return False
        except:
            print("✓ QueryCreate validation works (rejects empty)")
        
        print("✓ All schemas validated")
        return True
    except Exception as e:
        print(f"✗ Schemas test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_database_connection():
    """Test database connection."""
    print("\n" + "=" * 50)
    print("TEST: Database Connection")
    print("=" * 50)
    
    try:
        from app.db import init_db, engine
        from sqlalchemy import text
        
        # Try to connect
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
        
        print("✓ Database connection successful")
        
        # Initialize tables
        await init_db()
        print("✓ Database tables created/verified")
        
        return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        print("\n  Make sure PostgreSQL is running:")
        print("  docker-compose up -d postgres")
        return False


async def test_document_service():
    """Test document service operations."""
    print("\n" + "=" * 50)
    print("TEST: Document Service")
    print("=" * 50)
    
    try:
        from app.db.session import async_session_maker
        from app.services.document_service import DocumentService
        from app.schemas.document import DocumentCreate
        
        async with async_session_maker() as db:
            service = DocumentService(db)
            
            # Test checksum calculation
            checksum = service.calculate_checksum("test content")
            assert len(checksum) == 64  # SHA-256 hex
            print("✓ Checksum calculation works")
            
            # Test section parsing
            content = """# Main Title

This is the intro.

## Section One

Content for section one.

## Section Two

Content for section two.
"""
            sections = service._parse_sections(content)
            assert len(sections) == 3  # Main + 2 sections
            print(f"✓ Section parsing works ({len(sections)} sections found)")
            
            # Test create document
            test_doc = DocumentCreate(
                file_path="__test__/test_doc.md",
                content=content,
            )
            
            # Check if test doc exists, delete if so
            existing = await service.get_by_file_path("__test__/test_doc.md")
            if existing:
                await service.delete(existing.id)
                await db.commit()
            
            doc = await service.create(test_doc)
            await db.commit()
            
            assert doc.id is not None
            assert doc.file_path == "__test__/test_doc.md"
            assert len(doc.sections) == 3
            print(f"✓ Document created with ID: {doc.id}")
            print(f"✓ Document has {len(doc.sections)} sections")
            
            # Cleanup
            await service.delete(doc.id)
            await db.commit()
            print("✓ Test document cleaned up")
            
        return True
    except Exception as e:
        print(f"✗ Document service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_search_service():
    """Test ChromaDB search service."""
    print("\n" + "=" * 50)
    print("TEST: Search Service (ChromaDB)")
    print("=" * 50)
    
    try:
        from app.services.search_service import search_service
        from app.config import settings
        
        if not settings.openai_api_key:
            print("⚠ Skipping search test - OPENAI_API_KEY not set")
            return True
        
        # Initialize
        await search_service.initialize()
        print("✓ Search service initialized")
        
        # Get stats
        stats = await search_service.get_collection_stats()
        print(f"✓ Collection stats: {stats}")
        
        # Test adding a document
        from uuid import uuid4
        test_id = uuid4()
        
        await search_service.add_section(
            section_id=test_id,
            content="This is a test document about Python programming and FastAPI.",
            metadata={
                "document_id": str(uuid4()),
                "file_path": "__test__/search_test.md",
                "section_title": "Test Section",
            },
        )
        print("✓ Test section added to ChromaDB")
        
        # Test search
        results = await search_service.search("Python FastAPI", n_results=5)
        assert len(results) > 0
        print(f"✓ Search returned {len(results)} results")
        
        # Cleanup
        await search_service.delete_section(test_id)
        print("✓ Test section cleaned up")
        
        return True
    except Exception as e:
        print(f"✗ Search service test failed: {e}")
        print("\n  Make sure ChromaDB is running:")
        print("  docker-compose up -d chromadb")
        import traceback
        traceback.print_exc()
        return False


async def test_api_routes():
    """Test that API routes are properly configured."""
    print("\n" + "=" * 50)
    print("TEST: API Routes")
    print("=" * 50)
    
    try:
        from app.main import app
        from fastapi.testclient import TestClient
        
        # Note: TestClient is sync, but good for basic route testing
        client = TestClient(app)
        
        # Test root endpoint
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        print("✓ Root endpoint works")
        
        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200
        print("✓ Health endpoint works")
        
        # Test documents endpoint
        response = client.get("/api/documents")
        assert response.status_code == 200
        print("✓ Documents endpoint works")
        
        # Test queries endpoint
        response = client.get("/api/queries")
        assert response.status_code == 200
        print("✓ Queries endpoint works")
        
        # Test history endpoint
        response = client.get("/api/history")
        assert response.status_code == 200
        print("✓ History endpoint works")
        
        return True
    except Exception as e:
        print(f"✗ API routes test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("  PLUNO BACKEND TEST SUITE")
    print("=" * 60)
    
    results = {}
    
    # Run tests in order
    results["config"] = await test_config()
    results["models"] = await test_models()
    results["schemas"] = await test_schemas()
    results["database"] = await test_database_connection()
    
    if results["database"]:
        results["document_service"] = await test_document_service()
        results["search_service"] = await test_search_service()
        results["api_routes"] = await test_api_routes()
    else:
        print("\n⚠ Skipping service tests - database not available")
        results["document_service"] = None
        results["search_service"] = None
        results["api_routes"] = None
    
    # Summary
    print("\n" + "=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    skipped = 0
    
    for test_name, result in results.items():
        if result is True:
            print(f"  ✓ {test_name}")
            passed += 1
        elif result is False:
            print(f"  ✗ {test_name}")
            failed += 1
        else:
            print(f"  ⚠ {test_name} (skipped)")
            skipped += 1
    
    print(f"\n  Passed: {passed}, Failed: {failed}, Skipped: {skipped}")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
