# AI Clustering Module

This module constructs relationships between parsed OpenAPI endpoints and automatically clusters them into high-level enterprise workflows.

## Modules

### Graph Construction & Clustering (`graph_clustering.py`)
This script represents stripped OpenAPI endpoint operations (Contract A) as nodes in a NetworkX relationship graph. 

- **Edge Weights**: Formulates edge relationships based on path segment overlaps (base paths), matching path parameter schemas, and HTTP verb dependencies on the same endpoints.
- **Leiden/Louvain Fallback**: Runs community detection using label propagation or modularity greedy optimization algorithms to build cohesive communities.
- **Semantic Labeling**: Queries local Llama3 via Ollama chat endpoints to generate natural language names and descriptions. If Ollama is offline or Llama3 is missing, it falls back to a high-fidelity path-based heuristic model.
- **Database Storage**: Writes the resulting workflow mappings, endpoint-community associations, and audit logs into the SQLite schema.
