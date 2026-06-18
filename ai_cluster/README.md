# AI Workflow Discovery Engine

Clustering and discovery module for the **Enterprise MCP Workflow Proxy**. It analyzes and groups OpenAPI endpoints (Contract A) into high-level, production-grade workflows (Contract B) to generate the `workflow_mapping.json` routing configuration.

This module enforces 100% local execution for air-gapped Dell data centers, completely eliminating the risk of cloud data exfiltration or hallucinated execution.

## Setup

Use Python 3.11+ and install the project dependencies:

```bash
uv sync
```

The module uses:

- `pydantic v2`
- `instructor`
- `ollama`
- `pytest`
- Python `logging`

## Ollama Setup

Install Ollama on the local workstation or server, then pull llama3:

```bash
ollama pull llama3
ollama serve
```

No OpenAI, Anthropic, or cloud APIs are used.

## Configuration

Settings are read from environment variables in `ai_cluster/config/settings.py`:

- `OLLAMA_MODEL`, default `llama3`
- `OLLAMA_TIMEOUT`, default `120`
- `OLLAMA_MAX_RETRIES`, default `2`
- `OUTPUT_PATH`, default `ai_cluster/output/workflow_mapping.json`
- `LOG_LEVEL`, default `INFO`

## Execution Flow

1. Load Contract A JSON.
2. Validate endpoint schema and duplicate `operationId` values.
3. Build a Dell enterprise infrastructure prompt.
4. Send the prompt to local Ollama.
5. Validate the LLM response against Contract B.
6. Retry with validation feedback if the local model omits or duplicates APIs.
7. Deterministically repair structural assignment errors after exhausted retries.
8. Verify every endpoint belongs to exactly one workflow.
9. Write `workflow_mapping.json`.

Run:

```bash
python -m ai_cluster.main ai_cluster/output/contract_a_sample.json --output ai_cluster/output/workflow_mapping.json
```

## Sample Input

```json
[
  {
    "operationId": "getThermal",
    "method": "GET",
    "url": "/redfish/v1/Chassis/{server_id}/Thermal",
    "required_params": ["server_id"]
  },
  {
    "operationId": "getPower",
    "method": "GET",
    "url": "/redfish/v1/Chassis/{server_id}/Power",
    "required_params": ["server_id"]
  }
]
```

## Sample Output

```json
{
  "workflows": [
    {
      "workflow_name": "server_health_monitoring",
      "required_params": ["server_id"],
      "underlying_api_calls": ["getThermal", "getPower"],
      "confidence": 0.94,
      "reasoning": [
        "shared monitoring semantics",
        "common health-related operations"
      ]
    }
  ]
}
```

## Testing

```bash
pytest ai_cluster/tests
```

The tests cover prompt generation, JSON file parsing, Contract A validation,
Contract B schema validation, duplicate detection, and missing API detection.
