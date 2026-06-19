# Core Module

This module defines common settings, exception types, Pydantic models, and database managers shared across both design-time and runtime environments.

## Modules

### Database Manager (`database.py`)
Provides SQLite persistence for OpenAPI specifications (Contract A) and clustered workflow mappings (Contract B). It handles connection pooling, table schema initialization, and transactional writes/reads for human-in-the-loop governance.

### Configuration (`config.py`)
Loads and validates environment variables via Pydantic settings. It exposes single-source-of-truth settings for directories, mock targets, and executor choices.

### Models (`models.py`)
Declares structural schemas for Contract A endpoints and required parameters, enforcing stripping heuristics that remove descriptions and response models to fit context budgets.

## Integration
- The clustering CLI writes ingested specs and Leiden communities into the SQLite schema.
- The FastAPI governance API queries active states, metrics, and logs audit events directly through `database.py`.
- The FastMCP server dynamically queries approved workflows to expose them as MCP tools.
