# Dell Enterprise MCP Proxy Platform — CLI Reference

> **Version:** 0.1.0  
> **Entry point:** `dell-mcp`  
> **Discovery method:** Live `--help` interrogation of every command and subcommand  
> **Generated:** 2026-06-21

---

## Table of Contents

1. [Installation](#installation)
2. [Global Options](#global-options)
3. [Command Hierarchy](#command-hierarchy)
4. [overview](#overview)
5. [health](#health)
6. [cluster](#cluster)
   - [cluster run](#cluster-run)
   - [cluster summary](#cluster-summary)
   - [cluster graph](#cluster-graph)
7. [governance](#governance)
   - [governance pending](#governance-pending)
   - [governance approved](#governance-approved)
   - [governance rejected](#governance-rejected)
   - [governance review](#governance-review)
   - [governance approve](#governance-approve)
   - [governance reject](#governance-reject)
8. [compatibility](#compatibility)
   - [compatibility validate](#compatibility-validate)
   - [compatibility explain](#compatibility-explain)
   - [compatibility dashboard](#compatibility-dashboard)
   - [compatibility rules](#compatibility-rules)
   - [compatibility device](#compatibility-device)
9. [runtime](#runtime)
   - [runtime tools](#runtime-tools)
   - [runtime reload](#runtime-reload)
   - [runtime execute](#runtime-execute)
10. [ansible](#ansible)
    - [ansible preview](#ansible-preview)
    - [ansible export](#ansible-export)
11. [audit](#audit)
    - [audit events](#audit-events)
    - [audit executions](#audit-executions)
    - [audit summary](#audit-summary)
12. [system](#system)
    - [system topology](#system-topology)
13. [diagnostics](#diagnostics)
    - [diagnostics db](#diagnostics-db)
    - [diagnostics api](#diagnostics-api)
    - [diagnostics compatibility](#diagnostics-compatibility)
    - [diagnostics runtime](#diagnostics-runtime)
14. [Common Workflows](#common-workflows)
15. [Troubleshooting](#troubleshooting)
16. [Exit Codes](#exit-codes)
17. [Appendix: Complete Command Tree](#appendix-complete-command-tree)
18. [Documentation Statistics](#documentation-statistics)

---

## Installation

### Prerequisites

| Requirement | Version |
|---|---|
| Python | ≥ 3.10 |
| uv | Latest |
| SQLite | Bundled with Python |
| Ollama + Llama3 | Optional (AI labeling) |

### Setup

```powershell
# 1. Clone the repository
git clone https://github.com/Bit-Aure/DELL_MCP
cd DELL_MCP

# 2. Sync all dependencies
uv sync

# 3. Install the CLI package in editable mode
uv pip install -e .

# 4. Activate the virtual environment (Windows PowerShell)
.venv\Scripts\Activate.ps1

# 5. Verify installation
dell-mcp --help
```

> **Alternative (no activation required):** Prefix every command with `uv run`:
> ```bash
> uv run dell-mcp --help
> ```

---

## Global Options

These options apply to the `dell-mcp` root command and are inherited contextually by subcommands.

```
Usage: dell-mcp [OPTIONS] COMMAND [ARGS]...

  Dell Enterprise MCP Proxy Platform Infrastructure Command Center CLI
```

| Option | Short | Type | Description |
|---|---|---|---|
| `--json` | | flag | Enable machine-readable JSON output mode |
| `--verbose` | `-v` | flag | Enable verbose outputs with additional detail |
| `--debug` | | flag | Enable full debug mode with Python tracebacks |
| `--install-completion` | | flag | Install shell tab-completion for the current shell |
| `--show-completion` | | flag | Print completion script for manual installation |
| `--help` | | flag | Show help message and exit |

### Global Option Examples

```bash
# Run any command in JSON mode (machine-readable output)
dell-mcp --json overview

# Run with verbose logging
dell-mcp --verbose cluster summary

# Run with full debug tracebacks on error
dell-mcp --debug governance pending
```

---

## Command Hierarchy

```
dell-mcp
├── overview                          Executive control plane dashboard
├── health                            Subsystem health status matrix
├── cluster                           AI Ingestion and Clustering Engine
│   ├── run                           Ingest OpenAPI spec and cluster endpoints
│   ├── summary                       Display clustering statistics
│   └── graph                         Print graph node and edge totals
├── governance                        Human-in-the-Loop Governance console
│   ├── pending                       List workflows awaiting approval
│   ├── approved                      List certified approved workflows
│   ├── rejected                      List rejected workflows
│   ├── review    <workflow_id>        Review workflow steps and metadata
│   ├── approve   <workflow_id>        Approve a workflow for execution
│   └── reject    <workflow_id>        Reject a workflow with reason
├── compatibility                     Compatibility Intelligence Layer
│   ├── validate  <workflow_id>        Pre-flight hardware verification
│   ├── explain   <workflow_id>        Render DAG dependency rules tree
│   ├── dashboard <workflow_id>        Executive Go/No-Go decision cockpit
│   ├── rules                         Print active compatibility rules catalog
│   └── device    <ip>                Retrieve cached device facts
├── runtime                           FastMCP and Execution Engine
│   ├── tools                         List all registered FastMCP tools
│   ├── reload                        Hot-refresh tool mapping catalog
│   └── execute   <tool>              Simulate/execute workflow steps
├── ansible                           Ansible Playbook Enrichment Exporter
│   ├── preview   <workflow_id>        Render enriched YAML playbook
│   └── export    <workflow_id>        Export playbook to local file
├── audit                             Audit Ledger and Security Compliance
│   ├── events                        Print approval/rejection event log
│   ├── executions                    Print full execution history ledger
│   └── summary                       Print aggregated compliance counts
├── system                            Platform System Structures
│   └── topology                      Print datacenter topology hierarchy
└── diagnostics                       Subsystem Diagnostics Reports
    ├── db                            Database health and integrity check
    ├── api                           API gateway network diagnostics
    ├── compatibility                 Compatibility engine diagnostics
    └── runtime                       Tool runtime registration diagnostics
```

---

## overview

Display the executive overview control plane dashboard.

### Usage

```bash
dell-mcp overview [OPTIONS]
```

### Description

Renders a full-screen executive dashboard showing:
- Platform subsystem status (Database, Governance, Compatibility, FastMCP, Runtime)
- Workflow distribution (Total / Approved / Pending / Rejected counts)
- Operational metrics (Endpoints ingested, Compatibility rules, Device inventory, Executions, Violations blocked)

### Options

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `--watch` | | flag | false | Watch dashboard in real-time (live refresh) |
| `--interval` | `-i` | INTEGER | `5` | Watch update interval in seconds |
| `--help` | | flag | | Show help and exit |

### Examples

```bash
# Display one-shot overview dashboard
dell-mcp overview

# Live-refresh dashboard every 5 seconds
dell-mcp overview --watch

# Live-refresh every 10 seconds
dell-mcp overview --watch --interval 10

# JSON output for programmatic consumption
dell-mcp --json overview
```

---

## health

Display the platform subsystems health status Matrix.

### Usage

```bash
dell-mcp health [OPTIONS]
```

### Description

Renders a health status matrix for all five platform subsystems:

| Subsystem | What it checks |
|---|---|
| Database | SQLite connectivity and integrity |
| Governance | Governance middleware availability |
| Compatibility | Compatibility engine index and rule count |
| FastMCP | Proxy server availability on port 8000 |
| Runtime | Tool registration and MCP runtime status |

Status values: `HEALTHY` | `DEGRADED` | `UNAVAILABLE`

### Options

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `--watch` | | flag | false | Watch health metrics in real-time |
| `--interval` | `-i` | INTEGER | `5` | Watch update interval in seconds |
| `--help` | | flag | | Show help and exit |

### Examples

```bash
# One-shot health check
dell-mcp health

# Live health monitor
dell-mcp health --watch

# Live health every 30 seconds
dell-mcp health --watch --interval 30
```

---

## cluster

AI Ingestion and Clustering Engine — parses OpenAPI specifications, builds semantic relationship graphs, and discovers workflow clusters using Leiden community detection.

### Usage

```bash
dell-mcp cluster [OPTIONS] COMMAND [ARGS]...
```

### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

### Subcommands

| Subcommand | Description |
|---|---|
| `run` | Ingest OpenAPI spec and discover clusters |
| `summary` | Display clustering statistics |
| `graph` | Print graph node/edge totals |

---

### cluster run

Ingest OpenAPI paths and discover workflow clusters using Leiden clustering.

#### Usage

```bash
dell-mcp cluster run [OPTIONS]
```

#### Description

Executes the full AI ingestion pipeline:
1. Parses the OpenAPI specification (JSON or YAML)
2. Extracts all endpoints into Contract A format
3. Generates semantic embeddings using `all-MiniLM-L6-v2`
4. Constructs a NetworkX relationship graph with hybrid similarity scoring (semantic 25% + tag 25% + path 50%)
5. Applies Leiden community detection for workflow cluster discovery
6. Assigns governance status via the Governance Middleware interceptor
7. Persists all data to `data/governance.db`

#### Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--spec` | TEXT | `openapi.json` | Path to OpenAPI specification YAML or JSON file |
| `--help` | flag | | Show help and exit |

#### Examples

```bash
# Ingest the full Dell iDRAC 7.xx spec (714 endpoints)
dell-mcp cluster run --spec data/raw_specs/openapi-7.xx.yaml

# Ingest the sample demo spec (100 endpoints)
dell-mcp cluster run --spec data/openapi_sample.json

# Ingest a custom spec
dell-mcp cluster run --spec /path/to/my_openapi.json
```

#### Expected Output

```
✓ SUCCESS: Spec analysis completed. Discovered communities saved to governance.db.
```

---

### cluster summary

Display high-level operational statistics on discovered workflow clusters.

#### Usage

```bash
dell-mcp cluster summary [OPTIONS]
```

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp cluster summary
```

#### Expected Output

```
+------------------------------+
| Metric Property      | Value |
|----------------------+-------|
| Ingested Endpoints   | 714   |
| Discovered Workflows | 119   |
| Distinct Communities | 119   |
+------------------------------+
```

---

### cluster graph

Print relationship node and edge totals for the derived schema graph.

#### Usage

```bash
dell-mcp cluster graph [OPTIONS]
```

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp cluster graph
```

---

## governance

Human-in-the-Loop Governance console — manages the approval lifecycle of discovered workflow clusters before they can be executed against production infrastructure.

### Usage

```bash
dell-mcp governance [OPTIONS] COMMAND [ARGS]...
```

### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

### Subcommands

| Subcommand | Description |
|---|---|
| `pending` | List workflows awaiting approval |
| `approved` | List certified approved workflows |
| `rejected` | List rejected workflows |
| `review` | Review detailed API steps and metadata |
| `approve` | Approve a workflow for execution |
| `reject` | Reject a workflow with reason |

### Workflow States

| State | Code | Description |
|---|---|---|
| Pending | `0` | Awaiting human review |
| Approved | `1` | Certified for execution |
| Rejected | `2` | Blocked from execution |

---

### governance pending

List all workflows awaiting administrative audit and approval.

#### Usage

```bash
dell-mcp governance pending [OPTIONS]
```

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp governance pending
```

---

### governance approved

List all certified workflows approved for execution.

#### Usage

```bash
dell-mcp governance approved [OPTIONS]
```

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp governance approved
```

---

### governance rejected

List all rejected workflows blocked from execution.

#### Usage

```bash
dell-mcp governance rejected [OPTIONS]
```

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp governance rejected
```

---

### governance review

Review detailed API steps, parameters, and metadata for a specific workflow.

#### Usage

```bash
dell-mcp governance review [OPTIONS] WORKFLOW_ID
```

#### Arguments

| Argument | Type | Required | Description |
|---|---|---|---|
| `WORKFLOW_ID` | TEXT | ✅ Yes | ID of the workflow to review (e.g. `wf_c_d489c865`) |

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp governance review wf_c_d489c865
```

---

### governance approve

Approve a pending workflow, certifying it for runtime execution.

#### Usage

```bash
dell-mcp governance approve [OPTIONS] WORKFLOW_ID
```

#### Arguments

| Argument | Type | Required | Description |
|---|---|---|---|
| `WORKFLOW_ID` | TEXT | ✅ Yes | ID of the workflow to approve |

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp governance approve wf_c_d489c865
```

---

### governance reject

Reject a workflow, blocking it from execution and registering a safety explanation.

#### Usage

```bash
dell-mcp governance reject [OPTIONS] WORKFLOW_ID
```

#### Arguments

| Argument | Type | Required | Description |
|---|---|---|---|
| `WORKFLOW_ID` | TEXT | ✅ Yes | ID of the workflow to reject |

#### Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--reason` | TEXT | `Violates datacenter safety policies` | Rejection explanation reason |
| `--help` | flag | | Show help and exit |

#### Examples

```bash
# Reject with default reason
dell-mcp governance reject wf_c_d489c865

# Reject with custom safety reason
dell-mcp governance reject wf_c_d489c865 --reason "Unauthorized firmware downgrade path detected"
```

---

## compatibility

Compatibility Intelligence Layer — performs pre-flight hardware and firmware compatibility verification for workflows before they are executed against target PowerEdge servers.

### Usage

```bash
dell-mcp compatibility [OPTIONS] COMMAND [ARGS]...
```

### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

### Subcommands

| Subcommand | Description |
|---|---|
| `validate` | Pre-flight workflow verification against target device |
| `explain` | Render DAG dependency tree of compatibility rules |
| `dashboard` | Executive Go/No-Go deployment decision cockpit |
| `rules` | Print active compatibility rules catalog |
| `device` | Retrieve cached facts for a datacenter node |

---

### compatibility validate

Perform pre-flight verification on a workflow against a target device.

#### Usage

```bash
dell-mcp compatibility validate [OPTIONS] WORKFLOW_ID
```

#### Arguments

| Argument | Type | Required | Description |
|---|---|---|---|
| `WORKFLOW_ID` | TEXT | ✅ Yes | ID of the workflow to validate |

#### Options

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `--target-ip` | `-t` | TEXT | `192.168.0.120` | Target iDRAC/server IP address |
| `--help` | | flag | | Show help and exit |

#### Examples

```bash
# Validate against default test IP
dell-mcp compatibility validate wf_c_d489c865

# Validate against a specific production server
dell-mcp compatibility validate wf_c_d489c865 --target-ip 10.20.30.40

# Validate with short flag
dell-mcp compatibility validate wf_c_d489c865 -t 192.168.1.100
```

---

### compatibility explain

Render the topological DAG dependency tree of rules checking the workflow.

#### Usage

```bash
dell-mcp compatibility explain [OPTIONS] WORKFLOW_ID
```

#### Arguments

| Argument | Type | Required | Description |
|---|---|---|---|
| `WORKFLOW_ID` | TEXT | ✅ Yes | ID of the workflow to explain |

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp compatibility explain wf_c_d489c865
```

#### Description

Renders a visual tree showing all compatibility rules that will be evaluated for the given workflow, including prerequisite dependencies in topological order.

---

### compatibility dashboard

The executive decision cockpit verifying SAFE/BLOCKED deployment verdicts.

#### Usage

```bash
dell-mcp compatibility dashboard [OPTIONS] WORKFLOW_ID
```

#### Arguments

| Argument | Type | Required | Description |
|---|---|---|---|
| `WORKFLOW_ID` | TEXT | ✅ Yes | ID of the workflow to assess |

#### Options

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `--target-ip` | `-t` | TEXT | `192.168.0.120` | Target iDRAC/server IP address |
| `--help` | | flag | | Show help and exit |

#### Examples

```bash
# Run dashboard against default test server
dell-mcp compatibility dashboard wf_c_d489c865

# Run against a specific server
dell-mcp compatibility dashboard wf_c_d489c865 --target-ip 10.20.30.40
```

#### Description

Renders a full executive-grade decision panel showing:
- Workflow metadata (name, risk level, cluster size)
- Per-rule compatibility verdicts (PASS / FAIL / WARN)
- Final deployment verdict: `SAFE` or `BLOCKED`
- Compatibility score and risk score

---

### compatibility rules

Print the complete active compatibility rules catalog.

#### Usage

```bash
dell-mcp compatibility rules [OPTIONS]
```

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp compatibility rules
```

#### Description

Lists all compatibility rules currently registered in the database, including rule ID, name, type, domain, version, and effective date range.

---

### compatibility device

Retrieve stateful cached facts for a specific datacenter node.

#### Usage

```bash
dell-mcp compatibility device [OPTIONS] IP
```

#### Arguments

| Argument | Type | Required | Description |
|---|---|---|---|
| `IP` | TEXT | ✅ Yes | Target device IP address |

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Examples

```bash
# Retrieve cached facts for a server
dell-mcp compatibility device 192.168.0.120

# Retrieve facts for production node
dell-mcp compatibility device 10.20.30.40
```

#### Description

Returns the stateful device facts cached in the device inventory, including: device model, BIOS version, Lifecycle Controller version, firmware inventory, and last scan timestamp.

---

## runtime

FastMCP and Execution Engine — manages the FastMCP tool registration layer and executes approved workflows against target PowerEdge servers.

### Usage

```bash
dell-mcp runtime [OPTIONS] COMMAND [ARGS]...
```

### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

### Subcommands

| Subcommand | Description |
|---|---|
| `tools` | List all registered FastMCP tools |
| `reload` | Hot-refresh tool mapping catalog |
| `execute` | Simulate/execute workflow against target server |

---

### runtime tools

List all registered dynamic tools exposed to FastMCP clients.

#### Usage

```bash
dell-mcp runtime tools [OPTIONS]
```

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp runtime tools
```

#### Description

Queries the FastMCP proxy server and lists all currently registered tool definitions, including tool names, parameter schemas, and descriptions.

---

### runtime reload

Warm-refresh the server tool mapping catalog after metadata changes.

#### Usage

```bash
dell-mcp runtime reload [OPTIONS]
```

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp runtime reload
```

#### Description

Triggers a hot-reload of the FastMCP tool catalog without restarting the server. Use this after approving new workflows or modifying workflow metadata.

---

### runtime execute

Simulate and execute workflow steps against a target PowerEdge server.

#### Usage

```bash
dell-mcp runtime execute [OPTIONS]
```

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp runtime execute
```

---

## ansible

Ansible Playbook Enrichment Exporter — generates and exports enriched Ansible YAML playbooks from approved workflow clusters.

### Usage

```bash
dell-mcp ansible [OPTIONS] COMMAND [ARGS]...
```

### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

### Subcommands

| Subcommand | Description |
|---|---|
| `preview` | Render enriched YAML playbook with syntax highlighting |
| `export` | Export playbook to a local file |

---

### ansible preview

Render the enriched YAML playbook configuration utilizing Rich syntax highlighting.

#### Usage

```bash
dell-mcp ansible preview [OPTIONS] WORKFLOW_ID
```

#### Arguments

| Argument | Type | Required | Description |
|---|---|---|---|
| `WORKFLOW_ID` | TEXT | ✅ Yes | ID of the workflow to render as a playbook |

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp ansible preview wf_c_d489c865
```

#### Description

Renders a fully enriched Ansible YAML playbook to the terminal with syntax highlighting, showing all tasks, parameters, and iDRAC configuration steps derived from the workflow's API endpoint sequence.

---

### ansible export

Export the playbooks and prerequisite configuration settings to a local file.

#### Usage

```bash
dell-mcp ansible export [OPTIONS] WORKFLOW_ID
```

#### Arguments

| Argument | Type | Required | Description |
|---|---|---|---|
| `WORKFLOW_ID` | TEXT | ✅ Yes | ID of the workflow to export |

#### Options

| Option | Type | Description |
|---|---|---|
| `--output` | TEXT | Output file path for the exported playbook |
| `--help` | flag | Show help and exit |

#### Examples

```bash
# Export playbook to current directory
dell-mcp ansible export wf_c_d489c865

# Export with custom output path
dell-mcp ansible export wf_c_d489c865 --output ./playbooks/firmware_update.yml
```

---

## audit

Audit Ledger and Security Compliance logs — provides tamper-evident, hash-chained audit trail for all platform events.

### Usage

```bash
dell-mcp audit [OPTIONS] COMMAND [ARGS]...
```

### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

### Subcommands

| Subcommand | Description |
|---|---|
| `events` | Print database log entries for approvals, rejections, and reloads |
| `executions` | Print the complete historical execution ledger |
| `summary` | Print aggregated compliance counts |

---

### audit events

Print database log entries detailing approvals, rejections, and reloads.

#### Usage

```bash
dell-mcp audit events [OPTIONS]
```

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp audit events
```

#### Description

Renders the full audit event ledger, showing all governance actions (approvals, rejections, pipeline runs, reloads) with timestamps, actors, and tamper-evident hash chains.

---

### audit executions

Print the complete historical execution ledger for target nodes.

#### Usage

```bash
dell-mcp audit executions [OPTIONS]
```

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp audit executions
```

#### Description

Renders the full workflow execution history, showing every execution attempt against target servers with timestamps, workflow IDs, server IPs, and execution statuses.

---

### audit summary

Print aggregated counts for approvals, rejections, executions, and violations.

#### Usage

```bash
dell-mcp audit summary [OPTIONS]
```

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp audit summary
```

#### Description

Renders a concise compliance summary dashboard with aggregate totals for key governance metrics across the platform lifetime.

---

## system

Platform system structures — provides topology and infrastructure mapping views.

### Usage

```bash
dell-mcp system [OPTIONS] COMMAND [ARGS]...
```

### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

### Subcommands

| Subcommand | Description |
|---|---|
| `topology` | Print datacenter subsystem topology hierarchy |

---

### system topology

Print the complete datacenter subsystem topology mapping hierarchy.

#### Usage

```bash
dell-mcp system topology [OPTIONS]
```

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp system topology
```

#### Description

Renders the full topology tree of all platform subsystems, showing the architectural relationships between the CLI layer, governance layer, compatibility intelligence layer, FastMCP proxy, and the underlying Dell iDRAC infrastructure.

---

## diagnostics

Subsystem diagnostics reports — runs targeted health checks and connectivity probes for each platform component.

### Usage

```bash
dell-mcp diagnostics [OPTIONS] COMMAND [ARGS]...
```

### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

### Subcommands

| Subcommand | Description |
|---|---|
| `db` | Database health check and integrity diagnostics |
| `api` | API gateway network connection and port binding diagnostics |
| `compatibility` | Compatibility engine index and cached schemas diagnostics |
| `runtime` | Tool runtime registrations and API status diagnostics |

---

### diagnostics db

Run database health check and integrity diagnostics.

#### Usage

```bash
dell-mcp diagnostics db [OPTIONS]
```

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp diagnostics db
```

#### Description

Runs `PRAGMA integrity_check` on `data/governance.db`, reports table counts (endpoints, workflows, audit events, compatibility rules), and verifies WAL mode is active and functioning.

#### Expected Output Header

```
╭───────────────────── Governance DB Health Assessment ──────────────────────╮
```

---

### diagnostics api

Run API gateway network connection and port binding diagnostics.

#### Usage

```bash
dell-mcp diagnostics api [OPTIONS]
```

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp diagnostics api
```

#### Description

Probes the FastAPI proxy server at `http://localhost:8000`, verifying port availability, response latency, and endpoint registration status. Reports `CONNECTED` or `UNAVAILABLE`.

#### Expected Output Header

```
╭───────────────────── FastAPI Gateway Connection Check ─────────────────────╮
```

---

### diagnostics compatibility

Run compatibility engine index and cached schemas diagnostics.

#### Usage

```bash
dell-mcp diagnostics compatibility [OPTIONS]
```

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp diagnostics compatibility
```

#### Description

Verifies the compatibility engine's rule index, capability registry, device inventory cache, and DAG graph integrity. Reports active rule counts, domain coverage, and engine readiness.

#### Expected Output Header

```
╭───────────────────── Compatibility Layer Diagnostics ──────────────────────╮
```

---

### diagnostics runtime

Run tool runtime registrations and API status diagnostics.

#### Usage

```bash
dell-mcp diagnostics runtime [OPTIONS]
```

#### Options

| Option | Description |
|---|---|
| `--help` | Show help and exit |

#### Example

```bash
dell-mcp diagnostics runtime
```

#### Description

Queries the FastMCP proxy server for tool registrations, verifies the MCP runtime is correctly exposing approved workflows as callable tools, and reports total registered tool count and registration health.

#### Expected Output Header

```
╭───────────────────── FastMCP Tool Runtime Diagnostics ─────────────────────╮
```

---

## Common Workflows

### 1. Initial Platform Setup

```bash
# Step 1: Activate environment
.venv\Scripts\Activate.ps1

# Step 2: Ingest the full Dell iDRAC spec
dell-mcp cluster run --spec data/raw_specs/openapi-7.xx.yaml

# Step 3: Verify ingestion
dell-mcp cluster summary

# Step 4: Check platform health
dell-mcp health

# Step 5: View executive dashboard
dell-mcp overview
```

---

### 2. Governance Review Workflow

```bash
# List all workflows pending review
dell-mcp governance pending

# Review a specific workflow's API steps
dell-mcp governance review wf_c_d489c865

# Approve the workflow
dell-mcp governance approve wf_c_d489c865

# Or reject with reason
dell-mcp governance reject wf_c_d489c865 --reason "Unauthorized BIOS downgrade detected"

# Confirm final state
dell-mcp governance approved
```

---

### 3. Pre-flight Compatibility Check

```bash
# Run DAG rule tree to understand what rules apply
dell-mcp compatibility explain wf_c_d489c865

# Run pre-flight validation against target server
dell-mcp compatibility validate wf_c_d489c865 --target-ip 192.168.0.120

# View full executive Go/No-Go decision dashboard
dell-mcp compatibility dashboard wf_c_d489c865 --target-ip 192.168.0.120

# View all active compatibility rules
dell-mcp compatibility rules

# Check cached device facts
dell-mcp compatibility device 192.168.0.120
```

---

### 4. Ansible Playbook Export

```bash
# Preview the playbook in terminal
dell-mcp ansible preview wf_c_d489c865

# Export to file
dell-mcp ansible export wf_c_d489c865 --output ./playbooks/my_workflow.yml
```

---

### 5. Compliance Audit

```bash
# View all governance audit events
dell-mcp audit events

# View execution history
dell-mcp audit executions

# View compliance summary
dell-mcp audit summary
```

---

### 6. Full Platform Diagnostics

```bash
# Database integrity check
dell-mcp diagnostics db

# API gateway connectivity
dell-mcp diagnostics api

# Compatibility engine health
dell-mcp diagnostics compatibility

# Runtime tool registration check
dell-mcp diagnostics runtime
```

---

### 7. Live Monitoring

```bash
# Real-time dashboard (refreshes every 5s)
dell-mcp overview --watch

# Real-time health matrix
dell-mcp health --watch

# Custom refresh interval (every 15s)
dell-mcp overview --watch --interval 15
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'src'`

**Cause:** The bare `dell-mcp` command resolved to the system Python install instead of the project venv.

**Fix (preferred):**
```powershell
.venv\Scripts\Activate.ps1
dell-mcp --help
```

**Fix (alternative):**
```bash
uv run dell-mcp --help
```

---

### `database disk image is malformed`

**Cause:** A corrupted SQLite WAL file from an interrupted write or binary merge conflict.

**Fix:**
```powershell
# Remove corrupt files
Remove-Item data\governance.db, data\governance.db-wal, data\governance.db-shm -Force -ErrorAction SilentlyContinue

# Reinitialize the database
uv run python -c "from src.core.database import init_db_sync; init_db_sync()"

# Re-run clustering
dell-mcp cluster run --spec data/raw_specs/openapi-7.xx.yaml
```

---

### `FastMCP: DEGRADED` in health/overview

**Cause:** The FastMCP proxy server is not running.

**Fix:**
```bash
# Start the proxy server in a separate terminal
uv run uvicorn src.proxy.api:app --host 127.0.0.1 --port 8000
```

---

### Only 100 endpoints showing in overview

**Cause:** The sample spec `data/openapi_sample.json` was used instead of the full spec.

**Fix:**
```bash
dell-mcp cluster run --spec data/raw_specs/openapi-7.xx.yaml
```

---

### SQLite Database Locks

**Cause:** Multiple concurrent processes writing to the same database.

**Fix:** Ensure only one `cluster run` process runs at a time. The database uses WAL mode with a 5-second busy timeout, so brief contention resolves automatically.

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success — command completed normally |
| `1` | Error — command failed (check `--debug` for traceback) |
| `2` | Usage error — invalid arguments or missing required parameters |

---

## Appendix: Complete Command Tree

```
dell-mcp [--json] [--verbose/-v] [--debug] [--install-completion] [--show-completion] [--help]
│
├── overview [--watch] [--interval/-i INTEGER]
│
├── health [--watch] [--interval/-i INTEGER]
│
├── cluster
│   ├── run [--spec TEXT]
│   ├── summary
│   └── graph
│
├── governance
│   ├── pending
│   ├── approved
│   ├── rejected
│   ├── review     WORKFLOW_ID
│   ├── approve    WORKFLOW_ID
│   └── reject     WORKFLOW_ID [--reason TEXT]
│
├── compatibility
│   ├── validate   WORKFLOW_ID [--target-ip/-t TEXT]
│   ├── explain    WORKFLOW_ID
│   ├── dashboard  WORKFLOW_ID [--target-ip/-t TEXT]
│   ├── rules
│   └── device     IP
│
├── runtime
│   ├── tools
│   ├── reload
│   └── execute
│
├── ansible
│   ├── preview    WORKFLOW_ID
│   └── export     WORKFLOW_ID [--output TEXT]
│
├── audit
│   ├── events
│   ├── executions
│   └── summary
│
├── system
│   └── topology
│
└── diagnostics
    ├── db
    ├── api
    ├── compatibility
    └── runtime
```

---

## Documentation Statistics

| Metric | Count |
|---|---|
| **Total Command Groups** | 10 |
| **Total Subcommands** | 29 |
| **Total Commands (root + groups + subcommands)** | 40 |
| **Commands with Required Arguments** | 10 |
| **Commands with Optional Arguments** | 5 |
| **Global Options** | 6 |
| **Command-specific Options** | 8 |
| **Total Documented Options** | 14 |
| **Common Workflow Examples** | 7 |
| **Troubleshooting Scenarios** | 5 |
| **Documentation Generated** | 2026-06-21 |
| **Discovery Method** | Live `--help` interrogation |
| **CLI Version** | 0.1.0 |
