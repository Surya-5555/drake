import { apiRequest } from "@/lib/api/client";
import type {
  AuditEvent,
  GraphData,
  MetricsData,
  OverviewData,
  UpdateWorkflowPayload,
  WorkflowCluster,
} from "@/lib/types";

export const api = {
  overview: () => apiRequest<OverviewData>("/overview"),

  pendingWorkflows: () => apiRequest<WorkflowCluster[]>("/workflows/pending"),

  approveWorkflow: (workflowId: string) =>
    apiRequest<void>(`/workflows/${encodeURIComponent(workflowId)}/approve`, {
      method: "POST",
    }),

  rejectWorkflow: (workflowId: string, reason: string) =>
    apiRequest<void>(`/workflows/${encodeURIComponent(workflowId)}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  updateWorkflow: ({
    workflowId,
    payload,
  }: {
    workflowId: string;
    payload: UpdateWorkflowPayload;
  }) =>
    apiRequest<WorkflowCluster>(`/workflows/${encodeURIComponent(workflowId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  reloadMcp: () =>
    apiRequest<void>("/mcp/reload", {
      method: "POST",
    }),

  graph: () => apiRequest<GraphData>("/graph"),

  metrics: () => apiRequest<MetricsData>("/metrics"),

  auditEvents: () => apiRequest<AuditEvent[]>("/audit/events"),
};
