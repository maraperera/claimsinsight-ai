import os
import re
from typing import List, Dict, Any, Optional
from openai import AzureOpenAI
from src.search.retriever import ClaimsRetriever


SYSTEM_PROMPT = """You are an expert insurance claims analyst AI assistant.
Your goal is to answer questions about insurance claims accurately using ONLY the provided document context.

Rules:
1. Base your answer strictly on the provided context. If the context does not contain enough information, state that clearly.
2. Provide precise, professional, and clear explanations.
3. Always cite your sources inline using [Source: <filename>, Page: <page_number>, Claim: <claim_id>].
4. Highlight critical metrics, fault assessments, injury details, or monetary figures when present in the context.
"""


class ClaimsRAGService:
    def __init__(
        self,
        retriever: Optional[ClaimsRetriever] = None,
        chat_deployment: Optional[str] = None
    ):
        self.retriever = retriever or ClaimsRetriever()
        self.chat_deployment = chat_deployment or os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-5-mini")
        
        aoai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        aoai_key = os.getenv("AZURE_OPENAI_API_KEY")
        
        if not aoai_endpoint or not aoai_key:
            raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be set.")
            
        clean_endpoint = re.sub(r"/openai/.*$", "", aoai_endpoint).rstrip("/")
        
        self.openai_client = AzureOpenAI(
            azure_endpoint=clean_endpoint,
            api_key=aoai_key,
            api_version="2024-06-01"
        )

    def _format_context(self, search_results: List[Dict[str, Any]]) -> str:
        formatted_chunks = []
        for i, hit in enumerate(search_results, 1):
            formatted_chunks.append(
                f"--- DOCUMENT CHUNK {i} ---\n"
                f"Claim ID: {hit['claim_id']}\n"
                f"Document Type: {hit['document_type']}\n"
                f"Source File: {hit['filename']} (Page {hit['page_number']})\n"
                f"Content:\n{hit['chunk_text']}\n"
            )
        return "\n".join(formatted_chunks)

    def answer_query(
        self,
        query: str,
        claim_id: Optional[str] = None,
        document_type: Optional[str] = None,
        top_k: int = 4
    ) -> Dict[str, Any]:
        retrieved_docs = self.retriever.hybrid_search(
            query=query,
            top_k=top_k,
            claim_id=claim_id,
            document_type=document_type
        )

        if not retrieved_docs:
            return {
                "query": query,
                "answer": "No relevant claim documents were found matching your criteria.",
                "sources": []
            }

        context_str = self._format_context(retrieved_docs)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Context documents:\n{context_str}\n\nUser Question: {query}"
            }
        ]

        # Note: Temperature is omitted to ensure full compatibility with gpt-5/reasoning models
        response = self.openai_client.chat.completions.create(
            model=self.chat_deployment,
            messages=messages
        )

        answer_text = response.choices[0].message.content

        sources = [
            {
                "claim_id": d["claim_id"],
                "document_type": d["document_type"],
                "filename": d["filename"],
                "page_number": d["page_number"],
                "score": d["score"]
            }
            for d in retrieved_docs
        ]

        return {
            "query": query,
            "answer": answer_text,
            "sources": sources
        }