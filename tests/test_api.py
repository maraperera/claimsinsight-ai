import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from src.api.main import app, get_rag_service
from src.rag.generator import ClaimsRAGService

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_rag_dependency():
    """Automatically mock the RAG service dependency for all API tests."""
    mock_service = MagicMock(spec=ClaimsRAGService)
    app.dependency_overrides[get_rag_service] = lambda: mock_service
    yield mock_service
    app.dependency_overrides.clear()


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "ClaimsInsight AI API"}


def test_query_endpoint_success(mock_rag_dependency):
    mock_rag_dependency.answer_query.return_value = {
        "query": "What are the injuries?",
        "answer": "The claimant sustained cervical spine strain.",
        "sources": [
            {
                "claim_id": "CLM-2026-1045",
                "document_type": "MEDICAL_DISCHARGE",
                "filename": "CLM-2026-1045_MED_226.pdf",
                "page_number": 1,
                "score": 0.033
            }
        ]
    }

    payload = {
        "query": "What are the injuries?",
        "claim_id": "CLM-2026-1045",
        "top_k": 3
    }
    response = client.post("/api/v1/claims/query", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "What are the injuries?"
    assert "cervical spine strain" in data["answer"]
    assert len(data["sources"]) == 1
    assert data["sources"][0]["claim_id"] == "CLM-2026-1045"


def test_query_validation_error_min_length():
    # Sending a query shorter than min_length=3 returns HTTP 422 Unprocessable Entity
    response = client.post("/api/v1/claims/query", json={"query": "a"})
    assert response.status_code == 422