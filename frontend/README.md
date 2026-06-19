# Dell MCP Governance Console

Production-oriented Next.js 15 frontend for the Dell Enterprise MCP Workflow
Proxy. It provides the human-in-the-loop governance and observability layer for
OpenAPI ingestion, NetworkX graph construction, Leiden clustering, Llama3
semantic labeling, workflow approval, and FastMCP registration.

## Setup

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Set the backend URL:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Backend Contracts

The UI expects typed FastAPI endpoints under `/api/v1`:

- `GET /overview`
- `GET /workflows/pending`
- `POST /workflows/{workflowId}/approve`
- `POST /workflows/{workflowId}/reject`
- `PATCH /workflows/{workflowId}`
- `POST /mcp/reload`
- `GET /graph`
- `GET /metrics`
- `GET /audit/events`

Responses may use snake_case; the API client normalizes payloads to camelCase
for the React layer. Request bodies use camelCase fields as documented in
`src/lib/types.ts`.

No mock data is hardcoded. Loading, empty, and error states are first-class so
integration issues are visible during governance review.

## Architecture

```
src/
├── app/                 # App Router pages
├── components/          # UI composition (shell, feature modules, shadcn/ui)
├── hooks/               # TanStack Query hooks
├── lib/
│   ├── api/             # HTTP client + endpoint functions
│   ├── types.ts         # Shared TypeScript contracts
│   ├── query-keys.ts    # React Query cache keys
│   └── utils.ts         # cn() and helpers
└── store/               # Zustand client state (graph filters, selection)
```

