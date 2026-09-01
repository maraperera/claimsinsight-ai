from typing import List, Optional
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural language question regarding claims", min_length=3)
    claim_id: Optional[str] = Field(default=None, description="Optional Claim ID filter (e.g. CLM-2026-1001)")
    document_type: Optional[str] = Field(default=None, description="Optional Document Type filter (e.g. POLICE_REPORT)")
    top_k: int = Field(default=4, ge=1, le=10, description="Number of context chunks to retrieve")


class SourceAttribution(BaseModel):
    claim_id: str
    document_type: str
    filename: str
    page_number: int
    score: float


class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: List[SourceAttribution]


class HealthResponse(BaseModel):
    status: str
    service: str