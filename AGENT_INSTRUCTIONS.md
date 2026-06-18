# Model Context Protocol Workflow Proxy — Agent Instructions

## Rules you must follow

Always refer to the main `README.md` for core architecture decisions. Never deviate from the decoupled compile-time/runtime stack without explicitly flagging the architectural conflict.

When expanding or modifying execution logic, always implement the interface pattern specified in `src/proxy/executors/base.py`:
- `BaseExecutor (Abstract Base Class)`
- `MockHTTPXExecutor(BaseExecutor)`
- `DellOMSDKExecutor(BaseExecutor)`

The dynamic tool definitions inside `server.py` must only call the orchestration wrapper `execute_workflow_route()`, which selects the target executor. Never invoke an HTTP client or hardware execution library directly inside server routes.

All design-time generation modules inside `ai_cluster/` must validate intermediate data contracts using strict Pydantic structures. Data boundaries passing from OpenAPI schemas (Contract A) to compiled workflow recipes (Contract B) must be fully validated before writing to disk.

The dynamic tool registration pipeline inside `src/proxy/server.py` must:
1. Extract string parameter placeholders within workflow step templates dynamically.
2. Construct valid python function code containing explicit signatures mapping to those parameters.
3. Expose explicit parameter definitions via `mcp.add_tool()` so that upstream clients can confidently perform schema reflection.

Local environment variables managed by `dotenv` must serve as the single source of truth for all environment configurations:
- `DELL_WORKFLOW_MAPPING_PATH`
- `DELL_EXECUTOR_TYPE`
- `MOCK_SERVER_URL`

Never hardcode file routes, server addresses, or driver choices inside module initializations.

System routing flags control target behavior at runtime. When `DELL_EXECUTOR_TYPE` is set to "omsdk", routes swap over to the native hardware integration tier; if configured to "httpx", traffic shifts seamlessly to virtual mock targets.

Continuous verification workflows must strictly check all submissions against code quality tooling. Any modified code must successfully pass checking via `black --check .`, code linting via `flake8 .`, strict type safety validation via `mypy .`, and functional regressions testing using `pytest` without errors.

Complete asynchronous processing is mandatory across the runtime layer. Any network request made via `httpx.AsyncClient` must await execution to prevent blocking the FastMCP main communication thread. If synchronous packages or legacy SDK drivers must be called inside an executor module, wrap those operations using `asyncio.to_thread` or a managed thread pool to guarantee isolation.

Multi-step workflows must support progressive pipeline verification. The execution engine must capture the results of each sequential underlying API step, monitor response codes, and append structural tracing metadata directly to the payload response to maximize execution transparency for auditing.

## Documentation Discipline

Every time you write or modify code inside a service folder under `src/` or `ai_cluster/` (parser, ai_clustering, proxy, executors, services), you must also create or update a `README.md` inside that exact same folder. This is mandatory, not optional — but it only applies to the folder you are actually working in. Never create documentation files anywhere else in the repo as a side effect of this rule.

Each service README should explain, in plain language: what this module does, what it takes as input and what it returns, the one or two design decisions behind how it's built, and how the rest of the system calls into it. Write in simple, clear English. No emojis, no marketing language, no filler words. Keep it short — a few well-written paragraphs is enough, not a wall of text.

If new code changes what an existing part of a README describes, rewrite that part so the doc matches the current code exactly. Do not leave the old description sitting there and just tack a new note underneath it. The README must always reflect what the code actually does right now, with no outdated sections left behind.
