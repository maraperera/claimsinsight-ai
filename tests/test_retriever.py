import pytest
from unittest.mock import MagicMock, patch
from src.rag.generator import ClaimsRAGService


def test_format_context():
    mock_retriever = MagicMock()
    service = ClaimsRAGService(retriever=mock_retriever, chat_deployment="gpt-4o-mini")

    sample_hits = [
        {
            "chunk_id": "chunk-1",
            "claim_id": "CLM-2026-1000",
            "document_type": "PHYSIO_NOTE",
            "filename": "CLM-2026-1000_PHY_3.pdf",
            "page_number": 1,
            "chunk_text": "Patient reports 35% loss of lumbar flexion.",
            "score": 0.85
        }
    ]

    context = service._format_context(sample_hits)
    assert "CLM-2026-1000" in context
    assert "CLM-2026-1000_PHY_3.pdf" in context
    assert "Patient reports 35% loss of lumbar flexion." in context


@patch("src.rag.generator.AzureOpenAI")
def test_answer_query_empty_retrieval(mock_openai):
    mock_retriever = MagicMock()
    mock_retriever.hybrid_search.return_value = []

    service = ClaimsRAGService(retriever=mock_retriever, chat_deployment="gpt-4o-mini")
    result = service.answer_query(query="Non-existent claim query")

    assert "No relevant claim documents were found" in result["answer"]
    assert len(result["sources"]) == 0