import os
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
)

INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME", "claims-hybrid-index")


def get_search_index_client() -> SearchIndexClient:
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    api_key = os.getenv("AZURE_SEARCH_ADMIN_KEY")
    if not endpoint or not api_key:
        raise ValueError("AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_ADMIN_KEY must be set.")
    return SearchIndexClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))


def create_or_update_claims_index(client: SearchIndexClient, index_name: str = INDEX_NAME) -> SearchIndex:
    fields = [
        SimpleField(name="chunk_id", type=SearchFieldDataType.String, key=True, filterable=True, sortable=True),
        SimpleField(name="claim_id", type=SearchFieldDataType.String, filterable=True, facetable=True, sortable=True),
        SimpleField(name="document_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="filename", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="source_uri", type=SearchFieldDataType.String),
        SimpleField(name="page_number", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
        SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, sortable=True),
        SearchableField(name="chunk_text", type=SearchFieldDataType.String, analyzer_name="standard"),
        SearchField(
            name="vector_embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="claims-vector-profile"
        ),
        SimpleField(name="indexed_at", type=SearchFieldDataType.String, filterable=True)
    ]

    vector_search = VectorSearch(
        profiles=[
            VectorSearchProfile(
                name="claims-vector-profile",
                algorithm_configuration_name="claims-hnsw-config"
            )
        ],
        algorithms=[
            HnswAlgorithmConfiguration(
                name="claims-hnsw-config"
            )
        ]
    )

    index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search)
    result = client.create_or_update_index(index)
    print(f"Azure AI Search: Successfully configured index '{result.name}'.")
    return result