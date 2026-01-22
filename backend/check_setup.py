import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def check_imports():
    
    errors = []
    
    try:
        from app.config import settings
        print("✓ app.config")
    except Exception as e:
        print(f"✗ app.config: {e}")
        errors.append(("app.config", e))

    try:
        from app.db import Base, TimestampMixin, get_db, init_db
        print("✓ app.db")
    except Exception as e:
        print(f"✗ app.db: {e}")
        errors.append(("app.db", e))
    
    # Models
    try:
        from app.models import (
            Document, DocumentSection, SectionDependency,
            Query, QueryStatus,
            EditSuggestion, SuggestionStatus,
            EditHistory, UserAction,
        )
        print("✓ app.models")
    except Exception as e:
        print(f"✗ app.models: {e}")
        errors.append(("app.models", e))
    
    # Schemas
    try:
        from app.schemas import (
            DocumentCreate, DocumentResponse, DocumentListResponse,
            QueryCreate, QueryResponse,
            SuggestionCreate, SuggestionResponse,
            HistoryCreate, HistoryResponse,
        )
        print("✓ app.schemas")
    except Exception as e:
        print(f"✗ app.schemas: {e}")
        errors.append(("app.schemas", e))
    
    # Services
    try:
        from app.services import DocumentService, HistoryService, SearchService
        print("✓ app.services")
    except Exception as e:
        print(f"✗ app.services: {e}")
        errors.append(("app.services", e))
    
    # AI
    try:
        from app.ai import process_query, SYSTEM_PROMPT
        print("✓ app.ai")
    except Exception as e:
        print(f"✗ app.ai: {e}")
        errors.append(("app.ai", e))
    
    # API Routes
    try:
        from app.api.routes import documents, queries, suggestions, history
        print("✓ app.api.routes")
    except Exception as e:
        print(f"✗ app.api.routes: {e}")
        errors.append(("app.api.routes", e))
    
    # Main app
    try:
        from app.main import app
        print("✓ app.main")
    except Exception as e:
        print(f"✗ app.main: {e}")
        errors.append(("app.main", e))
    
    # Summary
    print("\n" + "=" * 40)
    if errors:
        print(f"FAILED: {len(errors)} import(s) failed")
        for module, error in errors:
            print(f"  - {module}: {error}")
        return False
    else:
        print("SUCCESS: All imports working!")
        return True


def check_schema_validation():
    """Test schema validation."""
    print("\n" + "=" * 40)
    print("Checking schema validation...\n")
    
    from app.schemas import DocumentCreate, QueryCreate
    from pydantic import ValidationError
    
    # Valid document
    try:
        doc = DocumentCreate(file_path="test.md", content="# Test")
        print("✓ DocumentCreate accepts valid data")
    except Exception as e:
        print(f"✗ DocumentCreate failed: {e}")
        return False
    
    # Valid query
    try:
        query = QueryCreate(query_text="Update docs")
        print("✓ QueryCreate accepts valid data")
    except Exception as e:
        print(f"✗ QueryCreate failed: {e}")
        return False
    
    # Invalid query (empty)
    try:
        QueryCreate(query_text="")
        print("✗ QueryCreate should reject empty string")
        return False
    except ValidationError:
        print("✓ QueryCreate rejects empty string")
    
    print("\nSUCCESS: Schema validation working!")
    return True


def check_model_relationships():
    """Check model relationships are defined correctly."""
    print("\n" + "=" * 40)
    print("Checking model relationships...\n")
    
    from app.models import Document, DocumentSection, Query, EditSuggestion, EditHistory
    
    # Check Document -> Sections relationship
    assert hasattr(Document, 'sections'), "Document missing 'sections' relationship"
    print("✓ Document.sections relationship exists")
    
    # Check Document -> History relationship  
    assert hasattr(Document, 'history'), "Document missing 'history' relationship"
    print("✓ Document.history relationship exists")
    
    # Check DocumentSection -> Document relationship
    assert hasattr(DocumentSection, 'document'), "DocumentSection missing 'document' relationship"
    print("✓ DocumentSection.document relationship exists")
    
    # Check Query -> Suggestions relationship
    assert hasattr(Query, 'suggestions'), "Query missing 'suggestions' relationship"
    print("✓ Query.suggestions relationship exists")
    
    # Check EditSuggestion relationships
    assert hasattr(EditSuggestion, 'query'), "EditSuggestion missing 'query' relationship"
    assert hasattr(EditSuggestion, 'section'), "EditSuggestion missing 'section' relationship"
    print("✓ EditSuggestion relationships exist")
    
    print("\nSUCCESS: All relationships defined!")
    return True


if __name__ == "__main__":
    print("=" * 50)
    print("  PLUNO BACKEND - QUICK CHECK")
    print("=" * 50)
    
    all_passed = True
    
    all_passed &= check_imports()
    all_passed &= check_schema_validation()
    all_passed &= check_model_relationships()
    
    print("\n" + "=" * 50)
    if all_passed:
        print("  ALL CHECKS PASSED ✓")
    else:
        print("  SOME CHECKS FAILED ✗")
    print("=" * 50)
    
    sys.exit(0 if all_passed else 1)