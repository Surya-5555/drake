export type RiskLevel = "low" | "medium" | "high" | "critical";

export type PipelineStatus = "idle" | "running" | "complete" | "error" | "unknown";

export interface EndpointSummary {
  operationId: string;
  method: string;
  path: string;
}

export interface WorkflowCluster {
  id: string;
  workflowName: string;
  riskLevel: RiskLevel;
  clusterSize: number;
  confidence: number;
  generatedDescription: string;
  underlyingEndpoints: EndpointSummary[];
  communityId?: string;
}

export interface OverviewData {
  endpointCount: number;
  workflowCount: number;
  pendingReviewCount: number;
  registeredWorkflowCount: number;
  ingestionStatus: PipelineStatus;
  graphStatus: PipelineStatus;
  clusteringStatus: PipelineStatus;
  mcpRuntimeStatus: PipelineStatus;
}

export interface GraphNode {
  id: string;
  method: string;
  label: string;
  communityId: string;
  x?: number;
  y?: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
}

export interface GraphCommunity {
  id: string;
  workflowName: string;
  size: number;
  confidence?: number;
  color?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  communities: GraphCommunity[];
}

export interface WorkflowDistributionEntry {
  workflowName: string;
  endpointCount: number;
}

export interface MetricsData {
  endpointReductionRatio: number | string;
  workflowCount: number;
  tokenSavingsPercent: number;
  clusteringCoveragePercent: number;
  approvedCount: number;
  rejectedCount: number;
  pendingCount: number;
  rawEndpointCount: number;
  workflowDistribution: WorkflowDistributionEntry[];
}

export interface AuditEvent {
  id: string;
  eventType: string;
  status: string;
  workflowName?: string;
  description: string;
  actor: string;
  timestamp: string;
}

export interface UpdateWorkflowPayload {
  workflowName: string;
  generatedDescription: string;
}

export interface RejectWorkflowPayload {
  reason: string;
}
