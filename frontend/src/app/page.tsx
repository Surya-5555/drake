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
    <div className="space-y-8 max-w-6xl mx-auto relative">
      <section className="flex justify-between items-end relative">
        <div>
          <h2 className="text-3xl font-bold text-[rgb(var(--foreground))]">Overview</h2>
          <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))] max-w-xl">
            Monitor ingestion, graph clustering, approval posture, and MCP runtime registration from one governed surface.
          </p>
        </div>
        
        {/* Hand-drawn Annotation */}
        <div className="absolute top-0 right-10 hidden md:flex flex-col items-center rotate-6">
          <svg width="60" height="40" viewBox="0 0 60 40" fill="none" xmlns="http://www.w3.org/2000/svg" className="text-[rgb(var(--primary))] opacity-80 mb-2">
            <path d="M10 20C20 10 40 10 50 20M50 20L40 15M50 20L45 30" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span className="font-['Caveat'] text-2xl text-[rgb(var(--primary))] tracking-wide transform -rotate-6">Looks great!</span>
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <Card key={card.key} className="relative overflow-hidden group">
            <div className="absolute top-0 right-0 w-24 h-24 bg-[rgb(var(--primary))] opacity-10 rounded-bl-full -mr-4 -mt-4 transition-transform group-hover:scale-110"></div>
            <CardContent className="flex flex-col pt-6 relative z-10">
              <div className="w-10 h-10 rounded-xl bg-gray-50 flex items-center justify-center border border-[rgb(var(--border))] mb-4">
                <card.icon className="h-5 w-5 text-[rgb(var(--muted-foreground))]" />
              </div>
              <p className="text-sm font-medium text-[rgb(var(--muted-foreground))]">{card.label}</p>
              {isLoading ? (
                <Skeleton className="mt-2 h-10 w-20 rounded-lg" />
              ) : (
                <p className="mt-1 text-4xl font-bold text-[rgb(var(--foreground))]">
                  {data?.[card.key] ?? 0}
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </section>

      <Card className="overflow-hidden">
        <CardHeader className="bg-gray-50/50 border-b border-[rgb(var(--border))]">
          <CardTitle className="text-lg">Pipeline Status</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="grid md:grid-cols-4 divide-y md:divide-y-0 md:divide-x divide-[rgb(var(--border))]">
            {pipelineStages.map((stage) => {
              const value = data?.[stage.key];
              return (
                <div className="p-6 flex flex-col justify-between hover:bg-gray-50/50 transition-colors" key={stage.key}>
                  <div className="text-xs font-semibold text-[rgb(var(--muted-foreground))] uppercase tracking-wider">{stage.label}</div>
                  <div className="mt-4">
                    {isLoading ? (
                      <Skeleton className="h-6 w-24 rounded-full" />
                    ) : (
                      <Badge tone={statusTone(value)}>{value ?? "unknown"}</Badge>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Hand-drawn element for empty space decor */}
      <div className="absolute -bottom-20 -left-10 opacity-20 pointer-events-none hidden lg:block">
        <svg width="200" height="200" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="100" cy="100" r="80" stroke="currentColor" strokeWidth="2" strokeDasharray="10 10" className="text-[rgb(var(--primary))]"/>
          <path d="M60 100C60 80 80 60 100 60" stroke="currentColor" strokeWidth="3" strokeLinecap="round" className="text-[rgb(var(--primary))]"/>
        </svg>
      </div>
    </div>
  );
}
