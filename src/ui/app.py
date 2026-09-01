import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000/api/v1/claims/query"

st.set_page_config(page_title="ClaimsInsight AI", page_icon="📑", layout="wide")

st.title("📑 ClaimsInsight AI — Claims Reasoning Engine")
st.markdown("Search and analyze claims documents with grounded citations.")

with st.sidebar:
    st.header("Search Filters")
    claim_id_input = st.text_input("Claim ID Filter (Optional)", placeholder="e.g. CLM-2026-1045")
    doc_type_input = st.selectbox(
        "Document Type Filter",
        ["All", "POLICE_REPORT", "MEDICAL_DISCHARGE", "POLICY_SCHEDULE", "ESTIMATE"]
    )
    top_k = st.slider("Context Chunks (top_k)", min_value=1, max_value=8, value=3)

user_query = st.chat_input("Ask a question about claims...")

if user_query:
    st.chat_message("user").write(user_query)
    
    payload = {
        "query": user_query,
        "claim_id": claim_id_input if claim_id_input.strip() else None,
        "document_type": None if doc_type_input == "All" else doc_type_input,
        "top_k": top_k
    }

    with st.spinner("Analyzing claims documents..."):
        try:
            res = requests.post(API_URL, json=payload)
            if res.status_code == 200:
                data = res.json()
                with st.chat_message("assistant"):
                    st.markdown(data["answer"])
                    
                    if data.get("sources"):
                        st.markdown("---")
                        st.markdown("**Sources & Citations:**")
                        for s in data["sources"]:
                            st.caption(
                                f"📄 `{s['filename']}` | Claim: `{s['claim_id']}` | Type: `{s['document_type']}` | Page {s['page_number']} | Score: {s['score']:.4f}"
                            )
            else:
                st.error(f"API Error {res.status_code}: {res.text}")
        except Exception as e:
            st.error(f"Failed to connect to API: {str(e)}")