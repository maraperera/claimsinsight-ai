import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=True)

from src.rag.generator import ClaimsRAGService

if __name__ == "__main__":
    rag = ClaimsRAGService()
    
    test_question = "Summarize the collision incident and state who was found at fault."
    
    print(f"Asking: '{test_question}'\n")
    result = rag.answer_query(query=test_question, top_k=3)
    
    print("=== AI RESPONSE ===")
    print(result["answer"])
    print("\n=== SOURCES CITED ===")
    for src in result["sources"]:
        print(f"- {src['filename']} (Claim: {src['claim_id']}, Page {src['page_number']})")