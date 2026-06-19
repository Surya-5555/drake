"use client";

import { useMemo, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  ReactFlowProvider,
  type Edge,
  type Node,
} from "reactflow";

import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useGraph } from "@/hooks/use-graph";
import type { GraphCommunity, GraphNode } from "@/lib/types";
import { useReviewStore } from "@/store/review-store";

const palette = [
  "#0f766e",
  "#2563eb",
  "#7c3aed",
  "#b45309",
  "#be123c",
  "#15803d",
  "#334155",
  "#0891b2",
];

function layoutNodes(nodes: GraphNode[], communityColor: Map<string, string>): Node[] {
  const communityOffsets = new Map<string, number>();

  return nodes.map((node, index) => {
    const communityIndex = communityOffsets.get(node.communityId) ?? 0;
    communityOffsets.set(node.communityId, communityIndex + 1);

    let commHash = 0;
    for (let i = 0; i < node.communityId.length; i++) {
      commHash = (commHash << 5) - commHash + node.communityId.charCodeAt(i);
      commHash |= 0;
    }
    const safeCommId = Math.abs(commHash % 20);

    const hasPosition = node.x !== undefined && node.y !== undefined;
    const position = hasPosition
      ? { x: node.x!, y: node.y! }
      : {
          x: (communityIndex % 5) * 220 + safeCommId * 60,
          y: Math.floor(communityIndex / 5) * 120 + index * 8,
        };

    return {
      id: node.id,
      position,
      data: {
        label: `${node.method} ${node.label}`,
        communityId: node.communityId,
        method: node.method,
      },
      style: {
        borderLeft: `6px solid ${communityColor.get(node.communityId) ?? "#64748b"}`,
        width: 190,
      },
    };
  });
}

function GraphCanvas() {
  const { data, isLoading, error } = useGraph();
  const { graphClusterFilter, selectedWorkflowId, setGraphClusterFilter } =
    useReviewStore();
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedCommunity, setSelectedCommunity] = useState<GraphCommunity | null>(
    null,
  );

  const communityColor = useMemo(() => {
    const map = new Map<string, string>();
    data?.communities.forEach((community, index) => {
      map.set(community.id, community.color ?? palette[index % palette.length]);
    });
    return map;
  }, [data]);

  const filteredNodes = useMemo(() => {
    if (!data) return [];
    return data.nodes.filter(
      (node) => !graphClusterFilter || node.communityId === graphClusterFilter,
    );
  }, [data, graphClusterFilter]);

  const nodes: Node[] = useMemo(
    () => layoutNodes(filteredNodes, communityColor),
    [communityColor, filteredNodes],
  );

  const edges: Edge[] = useMemo(() => {
    if (!data) return [];
    const visible = new Set(nodes.map((node) => node.id));
    return data.edges
      .filter((edge) => visible.has(edge.source) && visible.has(edge.target))
      .map((edge) => ({ id: edge.id, source: edge.source, target: edge.target }));
  }, [data, nodes]);

  if (error) {
    return <ErrorState message={(error as Error).message} />;
  }

  if (isLoading) {
    return <Skeleton className="h-[620px] w-full" />;
  }

  if (!data?.nodes.length) {
    return (
      <EmptyState
        title="No graph data available"
        description="Endpoint graph nodes and Leiden communities will appear after backend graph construction completes."
      />
    );
  }

  const activeCommunity = selectedCommunity ??
    data.communities.find((community) => community.id === graphClusterFilter) ??
    null;

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
      <Card className="h-[620px] overflow-hidden">
        <ReactFlow
          edges={edges}
          fitView
          nodes={nodes}
          onNodeClick={(_, node) => {
            const graphNode = data.nodes.find((entry) => entry.id === node.id) ?? null;
            setSelectedNode(graphNode);
            setSelectedCommunity(
              data.communities.find(
                (community) => community.id === graphNode?.communityId,
              ) ?? null,
            );
          }}
          proOptions={{ hideAttribution: true }}
        >
          <MiniMap pannable zoomable />
          <Controls />
          <Background />
        </ReactFlow>
      </Card>

      <div className="space-y-4">
        {selectedWorkflowId || graphClusterFilter ? (
          <Card>
            <CardContent className="space-y-2 pt-4">
              <h3 className="text-sm font-semibold">Active filter</h3>
              {selectedWorkflowId ? (
                <p className="text-xs text-slate-600">
                  Workflow selection: <span className="font-mono">{selectedWorkflowId}</span>
                </p>
              ) : null}
              {graphClusterFilter ? (
                <p className="text-xs text-slate-600">
                  Community: <span className="font-mono">{graphClusterFilter}</span>
                </p>
              ) : null}
              <Button
                onClick={() => setGraphClusterFilter(null)}
                size="sm"
                variant="secondary"
              >
                Clear filter
              </Button>
            </CardContent>
          </Card>
        ) : null}

        {selectedNode ? (
          <Card>
            <CardContent className="space-y-2 pt-4">
              <h3 className="text-sm font-semibold">Endpoint inspection</h3>
              <p className="font-mono text-xs text-slate-700">
                {selectedNode.method} {selectedNode.label}
              </p>
              <Badge tone="neutral">Community {selectedNode.communityId}</Badge>
              {activeCommunity ? (
                <p className="text-xs text-slate-600">
                  Cluster: {activeCommunity.workflowName} ({activeCommunity.size} endpoints)
                </p>
              ) : null}
            </CardContent>
          </Card>
        ) : null}

        <Card>
          <CardContent className="space-y-3 pt-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Leiden Communities</h3>
              <Button
                onClick={() => {
                  setGraphClusterFilter(null);
                  setSelectedCommunity(null);
                }}
                size="sm"
                variant="secondary"
              >
                Clear
              </Button>
            </div>
            {data.communities.map((community) => (
              <button
                className="w-full rounded-md border border-slate-200 p-3 text-left hover:bg-slate-50"
                key={community.id}
                onClick={() => {
                  setGraphClusterFilter(community.id);
                  setSelectedCommunity(community);
                  setSelectedNode(null);
                }}
                type="button"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium">{community.workflowName}</span>
                  <span
                    aria-hidden="true"
                    className="h-3 w-3 rounded-full"
                    style={{
                      backgroundColor: communityColor.get(community.id) ?? "#64748b",
                    }}
                  />
                </div>
                <div className="mt-2 flex gap-2">
                  <Badge tone="neutral">{community.size} endpoints</Badge>
                  {community.confidence ? (
                    <Badge tone="default">
                      {Math.round(community.confidence * 100)}%
                    </Badge>
                  ) : null}
                </div>
              </button>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export function OpenApiGraph() {
  return (
    <ReactFlowProvider>
      <GraphCanvas />
    </ReactFlowProvider>
  );
}
