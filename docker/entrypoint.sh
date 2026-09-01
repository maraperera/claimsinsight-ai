#!/bin/bash
set -e

if [ "$1" = "pipeline" ]; then
    echo "Starting Lakehouse Data Pipeline (Bronze -> Silver -> Gold)..."
    exec python scripts/run_pipeline_docker.py
elif [ "$1" = "search-indexing" ]; then
    echo "Starting Azure AI Search Indexing (Gold -> AI Search)..."
    exec python scripts/run_search_indexing.py
else
    # Allow executing any arbitrary python/shell command passed to docker run
    exec "$@"
fi