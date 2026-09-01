import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from src.rag.generator import ClaimsRAGService
from src.api.schemas import QueryRequest, QueryResponse, HealthResponse
from fastapi.responses import RedirectResponse

load_dotenv()

rag_service: ClaimsRAGService = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_service
    # Initialize RAG service on startup
    rag_service = ClaimsRAGService()
    yield


app = FastAPI(
    title="ClaimsInsight AI - RAG API",
    description="Insurance claim analysis API powered by Azure AI Search & Azure OpenAI Foundry",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_rag_service() -> ClaimsRAGService:
    if rag_service is None:
        raise HTTPException(status_code=503, detail="RAG service not initialized")
    return rag_service

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")

@app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
def health_check():
    return {"status": "healthy", "service": "ClaimsInsight AI API"}


@app.post("/api/v1/claims/query", response_model=QueryResponse, tags=["Claims Intelligence"])
def query_claims(request: QueryRequest, service: ClaimsRAGService = Depends(get_rag_service)):
    try:
        result = service.answer_query(
            query=request.query,
            claim_id=request.claim_id,
            document_type=request.document_type,
            top_k=request.top_k
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))