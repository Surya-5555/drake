"use client";

import { Activity, Database, GitBranch, ServerCog } from "lucide-react";

import { ErrorState } from "@/components/feedback/error-state";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useOverview } from "@/hooks/use-overview";
import type { PipelineStatus } from "@/lib/types";

const cards = [
  { key: "endpointCount", label: "Raw Endpoints", icon: Database },
  { key: "workflowCount", label: "Discovered Workflows", icon: GitBranch },
  { key: "pendingReviewCount", label: "Pending Review", icon: Activity },
  { key: "registeredWorkflowCount", label: "Registered MCP Tools", icon: ServerCog },
] as const;

const pipelineStages = [
  { key: "ingestionStatus", label: "OpenAPI ingestion" },
  { key: "graphStatus", label: "NetworkX graph" },
  { key: "clusteringStatus", label: "Leiden clustering" },
  { key: "mcpRuntimeStatus", label: "FastMCP runtime" },
] as const;

function statusTone(
  value?: PipelineStatus,
): "success" | "warning" | "danger" | "neutral" {
  switch (value) {
    case "complete":
      return "success";
    case "running":
      return "warning";
    case "error":
      return "danger";
    default:
      return "neutral";
  }
}

export default function OverviewPage() {
  const { data, isLoading, error } = useOverview();

  if (error) {
    return <ErrorState message={(error as Error).message} />;
  }

  return (
    <div className="space-y-5">
      <section>
        <h2 className="text-xl font-semibold text-slate-950">Overview</h2>
        <p className="mt-1 text-sm text-slate-500">
          Monitor ingestion, graph clustering, approval posture, and MCP runtime
          registration from one governed surface.
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <Card key={card.key}>
            <CardContent className="flex items-center justify-between pt-4">
              <div>
                <p className="text-sm text-slate-500">{card.label}</p>
                {isLoading ? (
                  <Skeleton className="mt-2 h-8 w-20" />
                ) : (
                  <p className="mt-2 text-3xl font-semibold">
                    {data?.[card.key] ?? 0}
                  </p>
                )}
              </div>
              <card.icon className="h-8 w-8 text-sky-700" />
            </CardContent>
          </Card>
        ))}
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Pipeline Status</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {pipelineStages.map((stage) => {
            const value = data?.[stage.key];
            return (
              <div className="rounded-md border border-slate-200 p-3" key={stage.key}>
                <div className="text-xs uppercase text-slate-500">{stage.label}</div>
                <div className="mt-2">
                  {isLoading ? (
                    <Skeleton className="h-5 w-24" />
                  ) : (
                    <Badge tone={statusTone(value)}>{value ?? "unknown"}</Badge>
                  )}
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
