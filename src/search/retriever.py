import os
import re
from typing import List, Dict, Any, Optional
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AzureOpenAI


class ClaimsRetriever:
    def __init__(self, index_name: str = "claims-hybrid-index"):
        self.endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.admin_key = os.getenv("AZURE_SEARCH_ADMIN_KEY")
        self.aoai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.aoai_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.embedding_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")

        if not all([self.endpoint, self.admin_key, self.aoai_endpoint, self.aoai_key]):
            raise ValueError("Missing search or OpenAI configuration environment variables.")

        # Clean Azure OpenAI endpoint (remove trailing slashes and subpaths)
        clean_aoai_endpoint = re.sub(r"/openai/.*$", "", self.aoai_endpoint).rstrip("/")

        self.search_client = SearchClient(
            endpoint=self.endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(self.admin_key)
        )
        self.openai_client = AzureOpenAI(
            azure_endpoint=clean_aoai_endpoint,
            api_key=self.aoai_key,
            api_version="2024-02-01"
        )

    def _get_embedding(self, text: str) -> List[float]:
        # Using model=deployment_name is standard for the Azure OpenAI Python SDK
        response = self.openai_client.embeddings.create(
            input=text,
            model=self.embedding_deployment
        )
        return response.data[0].embedding

    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        claim_id: Optional[str] = None,
        document_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query_vector = self._get_embedding(query)
        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_k,
            fields="vector_embedding"
        )

        filter_exprs = []
        if claim_id:
            filter_exprs.append(f"claim_id eq '{claim_id}'")
        if document_type:
            filter_exprs.append(f"document_type eq '{document_type}'")

        filter_str = " and ".join(filter_exprs) if filter_exprs else None

        results = self.search_client.search(
            search_text=query,
            vector_queries=[vector_query],
            filter=filter_str,
            top=top_k,
            select=["chunk_id", "claim_id", "document_type", "filename", "page_number", "chunk_text"]
        )

        hits = []
        for doc in results:
            hits.append({
                "chunk_id": doc.get("chunk_id"),
                "claim_id": doc.get("claim_id"),
                "document_type": doc.get("document_type"),
                "filename": doc.get("filename"),
                "page_number": doc.get("page_number"),
                "chunk_text": doc.get("chunk_text"),
                "score": doc.get("@search.score")
            })
        return hits