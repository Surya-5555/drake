# Context: File Structure

Maintain the following file structure for the Dell MCP Proxy project:

```text
dell_mcp_proxy/
├── data/
│   ├── raw_specs/              # Ingested raw OpenAPI specs
│   └── output/                 # Generated workflow_mapping.json mapping file
├── ai_cluster/                 # Design-Time workflow discovery pipeline
│   ├── config/
│   ├── models/
│   ├── prompts/
│   ├── schemas/
│   ├── services/
│   └── utils/
├── src/                        # Runtime execution layer
│   ├── core/                   # Configurations, exceptions, shared models
│   ├── parser/                 # OpenAPI spec ingestion and schema utilities
│   ├── ai_clustering/          # Instructor/Ollama generation orchestrator
│   └── proxy/                  # FastMCP Server application
│       ├── executors/          # Deterministic execution drivers
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── dell_omsdk_executor.py
│       │   └── httpx_executor.py
│       └── server.py           # Server instantiation and dynamic tools loop
├── tests/
├── pyproject.toml              # Dependencies and strict formatting overrides
└── uv.lock
```
