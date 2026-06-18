# MCP Workflow Proxy — Problem Statement & Hackathon Brief

## 1. Problem Title
**Transforming Enterprise OpenAPI Specifications into Workflow-Oriented Model Context Protocol (MCP) Servers**

---

## 2. Background / Context

Enterprise IT infrastructure is managed through a multitude of API endpoints:

- **Dell PowerEdge Servers** expose the **iDRAC Redfish API** for server hardware management (power control, firmware updates, hardware inventory, health monitoring, etc.)
- **Dell OpenManage Enterprise (OME)** provides a REST API to automate data center monitoring, device discovery, alerting, firmware compliance, and configuration management at scale
- Numerous other IT infrastructure management products (storage arrays, networking switches, hyperconverged platforms, observability stacks) each expose their own REST/Redfish APIs

With the rise of Generative AI and agentic workflows, these APIs are increasingly being consumed as tools by AI agents, enabling natural-language-driven infrastructure automation. The **Model Context Protocol (MCP)**, introduced by Anthropic, has emerged as a standard for exposing tools, prompts, and resources to LLMs in a structured, discoverable way.

The current approach wraps each API endpoint as an MCP tool. Frameworks such as **FastMCP** can auto-generate MCP tool definitions directly from an OpenAPI (Swagger) specification — useful as a starting point, but introduces significant challenges at enterprise scale.

---

## 3. Core Problem

Directly converting an OpenAPI specification into MCP tools produces an **explosion of fine-grained tools** (often hundreds or thousands per API surface), causing:

- **Context Length Overload** — Hundreds of tool definitions consume a large portion of the LLM's finite context window, leaving less room for reasoning, conversation history, and output
- **Tool Selection Difficulty** — LLMs struggle to select the correct tool or sequence of tools from an overwhelming number of similar, low-level options
- **Lack of Workflow Semantics** — Raw API endpoints are CRUD-level operations. Real-world IT tasks (e.g., "update firmware on all servers in rack 5") require orchestrated sequences of multiple API calls with data flowing between them
- **No Abstraction Layer** — No mechanism exists to automatically group, compose, and abstract low-level API calls into meaningful, higher-level workflows that map to how IT operators actually work

**The challenge: Build a Workflow Proxy that sits between the raw OpenAPI specification and the MCP server, intelligently grouping granular API endpoints into cohesive, workflow-level MCP tools.**

---

## 4. Objectives / Desired Outcomes

1. **Ingest OpenAPI Specifications** — Accept one or more OpenAPI (v3.x) specification files as input
2. **Analyze & Cluster API Endpoints** — Automatically or semi-automatically group endpoints into logical, higher-level workflows (e.g., "Server Health Check", "Firmware Update Workflow", "Device Discovery & Inventory")
3. **Generate Workflow-Level MCP Tools** — Produce an MCP server exposing coarse-grained MCP tools, prompts, and/or resources — not every individual endpoint
4. **Preserve Composability** — Allow advanced users or agents to drill down into sub-steps of a workflow without losing the high-level abstraction
5. **Reduce Context Footprint** — Demonstrate measurable reduction in MCP tool count and total token count required to describe capabilities to an LLM
6. **Maintain Correctness** — Ensure generated workflow tools correctly orchestrate underlying API calls, handle parameters, and propagate responses

---

## 5. Scope

### In Scope
- Parsing and analyzing OpenAPI v3.x specification files (JSON or YAML)
- Designing a strategy (rule-based, AI-assisted, or hybrid) to cluster/group API endpoints into workflows
- Generating an MCP-compliant server (Python, TypeScript, or supported language) with workflow-level tools
- A configuration/mapping layer for users to customize/override auto-generated workflow groupings
- A demonstration using at least one real-world or representative OpenAPI spec (e.g., iDRAC Redfish API, OME REST API, or publicly available infrastructure API spec)
- Basic documentation and a demo showcasing the proxy with an MCP-compatible client (e.g., Claude Desktop, Cursor, Windsurf, or a custom agent)

### Out of Scope
- Building a full production-grade API gateway or service mesh
- Implementing authentication/authorization flows end-to-end (mocking/stubbing auth is acceptable)
- Creating a complete AI agent or chat interface (focus is on the MCP server/proxy layer)
- Supporting non-OpenAPI spec formats (GraphQL, gRPC, etc.) — optional stretch goal only

---

## 6. Constraints / Limitations

| Constraint | Detail |
|---|---|
| **Time** | Must be developed within the hackathon timeframe |
| **MCP Compatibility** | Output must be a valid MCP server conforming to the latest stable MCP specification |
| **OpenAPI Input** | Primary input format must be OpenAPI v3.x; Swagger 2.0 optional |
| **Language** | Python (recommended, given FastMCP ecosystem), TypeScript, or any language with MCP SDK support |
| **No Proprietary API Access Required** | Work with publicly available OpenAPI specs or mock APIs; no live iDRAC/OME hardware required |
| **Context Budget** | Target ~4,000 token tool-definition budget (guideline), vs. potentially 50,000+ tokens for raw 1:1 mapping |

---

## 7. Assumptions

- Participants are familiar with (or can quickly learn) REST APIs, OpenAPI specifications, and basic AI/LLM concepts
- Development environments with Python 3.10+ or Node.js 18+ are available
- MCP specification and SDK documentation is publicly available and provided as reference
- A representative OpenAPI spec (or set of specs) will be provided as a starting dataset; teams encouraged to test with additional specs
- Teams may use open-source or commercial LLM APIs (e.g., OpenAI, Anthropic) for intelligent workflow clustering at design-time, but the **core proxy logic must not require an LLM at runtime**

---

## 8. Target Users / Personas

| Persona | Need |
|---|---|
| **IT Infrastructure Operator** | Uses AI agents to manage servers/storage/networking. Wants to say "check health of all servers in rack 3" and have the agent execute the right API call sequence |
| **Platform Engineer / DevOps** | Integrates enterprise APIs into AI-powered automation platforms. Needs to onboard new APIs into the MCP ecosystem without hand-coding each tool |
| **AI Agent Developer** | Builds agentic workflows; needs a manageable, well-organized set of MCP tools an LLM can reason about — not a flat list of 500 raw endpoints |
| **Solution Architect** | Designs the overall AI-driven infrastructure management stack; needs a scalable API-to-MCP transformation pattern across multiple products |

---

## 9. Current State vs. Target State

### Current State
- Enterprise products expose rich REST/Redfish APIs with comprehensive OpenAPI specs
- FastMCP and similar frameworks produce a **1:1 mapping** (one tool per endpoint)
- A typical enterprise API spec contains **100–500+ endpoints** → 100–500+ MCP tools (far too many)
- No standard mechanism to compose low-level API endpoints into higher-level workflow tools
- Excessive context token consumption degrades agent performance and increases latency/cost

### Target State
- **Input:** One or more OpenAPI v3.x specifications (JSON/YAML)
- **Processing:** Proxy analyzes spec(s), identifies logical groupings (by resource, use-case, domain), composes multi-step workflows
- **Output:** Running MCP server exposing **10–30 workflow-level tools** (instead of 100–500), each representing a meaningful IT operation
- **Experience:** IT operator sees clean, intuitive capabilities — e.g., `server_health_check`, `firmware_update_workflow`, `device_inventory_report` — and accomplishes complex tasks with a single natural-language request
- **Extensibility:** New APIs onboarded by simply providing the OpenAPI spec; proxy handles the rest with minimal manual configuration
- **Transparency:** Each workflow tool includes metadata describing underlying API calls it orchestrates, enabling auditability and debugging

---

## 10. Success Metrics & Acceptance Criteria

| Metric | Target |
|---|---|
| **Tool Count Reduction** | ≥ 80% reduction vs. 1:1 OpenAPI-to-MCP mapping |
| **Context Token Reduction** | ≥ 70% reduction in total tokens consumed by tool definitions |
| **Workflow Coverage** | Generated workflows cover ≥ 80% of common IT operational use cases derivable from input spec |
| **Correctness** | Workflow tools correctly execute API call sequences and return accurate, aggregated results (via mock or live tests) |
| **Functional Demo** | Working end-to-end demo with MCP client invoking at least 3 distinct workflow tools against a mock or real API backend |
| **Onboarding Speed** | New OpenAPI spec ingested and converted into workflow-level MCP tools in under 5 minutes (excluding customization) |
| **Documentation** | Clear README, architecture diagram, and usage instructions provided |

---

## 11. Risks & Dependencies

- Access to OpenAPI specification files for target APIs (public repos)
- MCP SDK — Python: `mcp` package; TypeScript: `@modelcontextprotocol/sdk`
- FastMCP or similar framework (optional, as starting point or reference)
- Mock API server (e.g., Prism, WireMock) for testing without live hardware

---

## 12. Expected Deliverables

1. **Source Code** — Working MCP Workflow Proxy codebase hosted on a Git repository
2. **MCP Server** — Runnable MCP server generated by the proxy from at least one OpenAPI spec
3. **Workflow Definitions** — Documentation or configuration files showing mapping from raw API endpoints to workflow-level tools
4. **Demo** — Live or recorded demonstration showing:
   - Ingesting an OpenAPI spec
   - Generating workflow-level MCP tools
   - MCP client (or agent) invoking workflow tools and receiving results
5. **Architecture Documentation** — Brief architecture diagram and write-up explaining design, workflow clustering strategy, and key trade-offs
6. **Presentation / Pitch Deck** — Short presentation summarizing problem, approach, demo, and results

---

## 13. Evaluation Criteria

| Criterion | Weight |
|---|---|
| **Innovation & Approach** — Creativity/sophistication of workflow clustering strategy; AI-assisted analysis, semantic understanding, or novel heuristics | 25% |
| **Technical Execution** — Code quality, architecture, correctness, and robustness of the MCP Workflow Proxy | 25% |
| **Effectiveness (Tool Reduction)** — Demonstrated reduction in tool count and context token usage while maintaining workflow coverage | 20% |
| **Demo & Usability** — Quality of end-to-end demo; ease of onboarding a new OpenAPI spec; clarity of generated workflow tools | 15% |
| **Documentation & Presentation** — Clarity of architecture docs, README, and final pitch | 10% |
| **Stretch Goals** — Completion of any bonus stretch goals | 5% |

---

## 14. Stretch Goals (Bonus Points)

- **Multi-API Composition** — Ingest multiple OpenAPI specs from different products and generate cross-product workflow tools (e.g., provision a server via iDRAC then register it in OME)
- **Dynamic Workflow Discovery** — Use an LLM at design-time to automatically suggest workflow groupings based on API descriptions, parameter names, and resource relationships
- **Hierarchical Tool Exposure** — Implement a tiered MCP tool structure where the agent first sees high-level workflows and can "expand" a workflow to see its sub-steps as finer-grained tools on demand
- **Natural Language Workflow Definition** — Allow users to define new workflows in natural language (e.g., "check server health and update firmware if health is good"), which the proxy translates into the correct API call sequence
- **Caching & Optimization** — Implement intelligent caching of API responses within a workflow to minimize redundant calls
- **Support for Additional Spec Formats** — Extend the proxy to accept GraphQL schemas, gRPC `.proto` files, or AsyncAPI specs in addition to OpenAPI
- **Observability Dashboard** — Build a simple UI that visualizes the workflow-to-API mapping and execution traces
- **Automated Testing Suite** — Generate test cases for each workflow tool to validate correctness against the mock API

---

## 15. Reference Links

| Resource | Link |
|---|---|
| MCP Specification | https://spec.modelcontextprotocol.io |
| MCP GitHub | https://github.com/modelcontextprotocol |
| FastMCP GitHub | https://github.com/jlowin/fastmcp |
| FastMCP Docs | https://gofastmcp.com |
| OpenAPI Specification | https://spec.openapis.org/oas/v3.1.0 |
| Dell iDRAC Redfish API | https://developer.dell.com/apis/2978/versions/6.xx/docs/0Introduction.md |
| Dell OME REST API | https://developer.dell.com/apis/4378/versions/4.0.0 |
| Prism Mock API Server | https://github.com/stoplightio/prism |
| Anthropic MCP Blog Post | https://www.anthropic.com/news/model-context-protocol |