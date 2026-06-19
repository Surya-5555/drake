"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMetrics } from "@/hooks/use-metrics";

const colors = ["#0f766e", "#2563eb", "#7c3aed", "#b45309", "#be123c", "#15803d"];

function truncateLabel(value: string, max = 18) {
  return value.length > max ? `${value.slice(0, max)}…` : value;
}

export function MetricsDashboard() {
  const { data, isLoading, error } = useMetrics();

  if (error) {
    return <ErrorState message={(error as Error).message} />;
  }

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <Skeleton className="h-28" key={index} />
        ))}
      </div>
    );
  }

  if (!data) {
    return (
      <EmptyState
        title="Metrics unavailable"
        description="Operational metrics will appear once the backend metrics endpoint is available."
      />
    );
  }

  const stats = [
    ["Endpoint reduction", `${data.endpointReductionRatio}:1`],
    ["Workflow count", data.workflowCount],
    ["Token savings", `${data.tokenSavingsPercent}%`],
    ["Clustering coverage", `${data.clusteringCoveragePercent}%`],
    ["Approved", data.approvedCount],
    ["Rejected", data.rejectedCount],
    ["Pending", data.pendingCount],
    ["Raw endpoints", data.rawEndpointCount],
  ];

  const distribution = data.workflowDistribution.map((entry) => ({
    ...entry,
    shortName: truncateLabel(entry.workflowName),
  }));

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {stats.map(([label, value]) => (
          <Card key={label}>
            <CardContent className="pt-4">
              <p className="text-sm text-slate-500">{label}</p>
              <p className="mt-2 text-2xl font-semibold text-slate-950">{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Workflow Distribution</CardTitle>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer height="100%" width="100%">
              <BarChart data={distribution}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  angle={-25}
                  dataKey="shortName"
                  height={70}
                  interval={0}
                  textAnchor="end"
                  tick={{ fontSize: 11 }}
                />
                <YAxis />
                <Tooltip
                  formatter={(value) => [value, "Endpoints"]}
                  labelFormatter={(_, payload) => {
                    const entry = payload?.[0]?.payload as
                      | { workflowName?: string }
                      | undefined;
                    return entry?.workflowName ?? "";
                  }}
                />
                <Bar dataKey="endpointCount" fill="#0f766e" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Approval Posture</CardTitle>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer height="100%" width="100%">
              <PieChart>
                <Pie
                  data={[
                    { name: "Approved", value: data.approvedCount },
                    { name: "Rejected", value: data.rejectedCount },
                    { name: "Pending", value: data.pendingCount },
                  ]}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                  nameKey="name"
                  outerRadius={110}
                >
                  {colors.slice(0, 3).map((color) => (
                    <Cell fill={color} key={color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
