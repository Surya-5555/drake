"use client";

/* eslint-disable @typescript-eslint/no-explicit-any */

import dynamic from "next/dynamic";
import { useMemo, useState, useRef, useEffect } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useGraph } from "@/hooks/use-graph";
import type { GraphCommunity, GraphNode } from "@/lib/types";
import { useReviewStore } from "@/store/review-store";

// Dynamically import the force graph to avoid SSR window errors
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => <Skeleton className="h-[620px] w-full" />,
});

const palette = [
  "#0f766e", // teal
  "#2563eb", // blue
  "#7c3aed", // violet
  "#b45309", // amber
  "#be123c", // rose
  "#15803d", // green
  "#334155", // slate
  "#0891b2", // cyan
  "#c026d3", // fuchsia
  "#ea580c", // orange
];

function GraphCanvas() {
  const { data, isLoading, error } = useGraph();
  const { graphClusterFilter, selectedWorkflowId, setGraphClusterFilter } =
    useReviewStore();
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedCommunity, setSelectedCommunity] = useState<GraphCommunity | null>(
    null,
  );
  
  const fgRef = useRef<any>(null);

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

  const graphData = useMemo(() => {
    if (!data) return { nodes: [], links: [] };
    
    const visible = new Set(filteredNodes.map((n) => n.id));
    const nodes = filteredNodes.map((n) => ({
      ...n,
      id: n.id,
      name: `${n.method} ${n.label}`,
      color: communityColor.get(n.communityId) ?? "#64748b",
      val: 2, // Size of the node
    }));
    
    const links = data.edges
      .filter((edge) => visible.has(edge.source) && visible.has(edge.target))
      .map((edge) => ({
        source: edge.source,
        target: edge.target,
      }));
      
    return { nodes, links };
  }, [data, filteredNodes, communityColor]);

  // Handle smooth zooming when filter changes
  useEffect(() => {
    if (fgRef.current && graphData.nodes.length > 0) {
       setTimeout(() => {
         if (fgRef.current) fgRef.current.zoomToFit(400, 20);
       }, 500);
    }
  }, [graphClusterFilter, graphData]);

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
      <Card className="h-[620px] overflow-hidden bg-slate-50 relative">
        <ForceGraph2D
          ref={fgRef}
          graphData={graphData}
          nodeLabel={(node: any) => {
            const methodColors: Record<string, string> = {
              GET: "#10b981", POST: "#3b82f6", PUT: "#f59e0b", DELETE: "#ef4444", PATCH: "#8b5cf6"
            };
            const methodBg = methodColors[node.method] || "#64748b";
            
            return `
              <div style="background: rgba(15, 23, 42, 0.95); color: white; padding: 10px 14px; border-radius: 8px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1); font-family: Inter, system-ui, sans-serif; font-size: 13px; max-width: 300px; border: 1px solid rgba(255,255,255,0.1); backdrop-filter: blur(4px);">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                  <span style="background: ${methodBg}; color: white; font-weight: 700; font-size: 11px; padding: 2px 6px; border-radius: 4px; letter-spacing: 0.5px;">${node.method}</span>
                  <span style="color: #94a3b8; font-size: 11px; font-weight: 500;">Community ${node.communityId}</span>
                </div>
                <div style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; color: #e2e8f0; word-break: break-all; line-height: 1.4;">
                  ${node.label}
                </div>
              </div>
            `;
          }}
          linkColor={() => "#cbd5e1"}
          linkDirectionalArrowLength={2}
          linkDirectionalArrowRelPos={1}
          d3AlphaDecay={0.02}
          d3VelocityDecay={0.3}
          nodeCanvasObject={(node: any, ctx, globalScale) => {
            const size = 6;
            
            // 1. Draw the outer glow/ring (Community Workflow Color)
            ctx.beginPath();
            ctx.arc(node.x, node.y, size + 1.5, 0, 2 * Math.PI, false);
            ctx.fillStyle = node.color; // The Leiden Community color
            ctx.fill();

            // 2. HTTP Method Avatar Colors
            const methodColors: Record<string, string> = {
              GET: "#10b981",    // Emerald
              POST: "#3b82f6",   // Blue
              PUT: "#f59e0b",    // Amber
              DELETE: "#ef4444", // Red
              PATCH: "#8b5cf6"   // Violet
            };
            const methodBg = methodColors[node.method] || "#64748b";
            
            // 3. Draw the inner Avatar circle
            ctx.beginPath();
            ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
            ctx.fillStyle = methodBg;
            ctx.fill();

            // 4. Draw the SVG Path Icon (Only when zoomed in enough)
            if (globalScale > 1.2) {
              // Standard 24x24 Material Design Icons
              const svgPaths: Record<string, string> = {
                // Download/Arrow Down
                GET: "M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z",
                // Plus/Add Circle
                POST: "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5 11h-4v4h-2v-4H7v-2h4V7h2v4h4v2z",
                // Refresh/Sync
                PUT: "M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z",
                // Pencil/Edit
                PATCH: "M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z",
                // Trash
                DELETE: "M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"
              };

              const pathString = svgPaths[node.method] || svgPaths.GET;
              
              // Only create Path2D if we are in browser (Path2D exists)
              if (typeof Path2D !== "undefined") {
                const iconPath = new Path2D(pathString);
                
                const padding = size * 0.4;
                const iconSize = (size * 2) - (padding * 2);
                
                ctx.save();
                // Move to top-left of the icon box
                ctx.translate(node.x - iconSize / 2, node.y - iconSize / 2);
                // Scale the 24x24 SVG path down to our iconSize
                ctx.scale(iconSize / 24, iconSize / 24);
                
                ctx.fillStyle = "#ffffff";
                ctx.fill(iconPath);
                ctx.restore();
              }
            }
          }}
          onNodeClick={(node: any) => {
             const graphNode = data.nodes.find((entry) => entry.id === node.id) ?? null;
             setSelectedNode(graphNode);
             setSelectedCommunity(
               data.communities.find(
                 (community) => community.id === graphNode?.communityId,
               ) ?? null,
             );
          }}
          onEngineStop={() => {
            if (fgRef.current && !graphClusterFilter) {
               fgRef.current.zoomToFit(400, 20);
            }
          }}
        />
        {/* Helper text overlay */}
        <div className="absolute bottom-4 left-4 bg-white/80 backdrop-blur-sm px-3 py-1.5 rounded-md text-xs font-medium text-slate-500 shadow-sm pointer-events-none">
          Scroll to zoom • Drag background to pan • Drag nodes to interact
        </div>
      </Card>

      <div className="space-y-4 max-h-[620px] overflow-y-auto pr-2 custom-scrollbar">
        {selectedWorkflowId || graphClusterFilter ? (
          <Card>
            <CardContent className="space-y-2 pt-4">
              <h3 className="text-sm font-semibold">Active filter</h3>
              {selectedWorkflowId ? (
                <p className="text-xs text-slate-600 break-all">
                  Workflow selection: <span className="font-mono">{selectedWorkflowId}</span>
                </p>
              ) : null}
              {graphClusterFilter ? (
                <p className="text-xs text-slate-600 break-all">
                  Community: <span className="font-mono">{graphClusterFilter}</span>
                </p>
              ) : null}
              <Button
                onClick={() => setGraphClusterFilter(null)}
                size="sm"
                variant="secondary"
                className="w-full"
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
              <p className="font-mono text-xs text-slate-700 break-all">
                <span className="font-bold text-slate-900">{selectedNode.method}</span> {selectedNode.label}
              </p>
              <Badge tone="neutral" className="block w-fit">Community {selectedNode.communityId}</Badge>
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
            <div className="flex items-center justify-between sticky top-0 bg-white z-10 pb-2">
              <h3 className="text-sm font-semibold">Leiden Communities</h3>
              <Button
                onClick={() => {
                  setGraphClusterFilter(null);
                  setSelectedCommunity(null);
                }}
                size="sm"
                variant="secondary"
              >
                Clear All
              </Button>
            </div>
            {data.communities.map((community) => (
              <button
                className={`w-full rounded-md border p-3 text-left transition-colors ${
                  graphClusterFilter === community.id 
                    ? "bg-slate-100 border-slate-300" 
                    : "border-slate-200 hover:bg-slate-50"
                }`}
                key={community.id}
                onClick={() => {
                  setGraphClusterFilter(community.id);
                  setSelectedCommunity(community);
                  setSelectedNode(null);
                }}
                type="button"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium line-clamp-2">{community.workflowName}</span>
                  <span
                    aria-hidden="true"
                    className="h-3 w-3 rounded-full shrink-0"
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
  return <GraphCanvas />;
}
