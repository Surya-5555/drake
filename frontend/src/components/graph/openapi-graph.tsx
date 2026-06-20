"use client";

import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  MarkerType,
  type Node,
  type Edge,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "dagre";
import { useEffect, useMemo, useState } from "react";
import { TreeStructure, Desktop, TerminalWindow, Coins, Graph, CaretRight, CaretLeft, ListDashes, SidebarSimple } from "@phosphor-icons/react";

import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useGraph } from "@/hooks/use-graph";
import { useReviewStore } from "@/store/review-store";
import type { GraphCommunity, GraphNode } from "@/lib/types";

import { AtomieEdge } from "./atomie-edge";
import { VoidNode } from "./void-node";

const nodeTypes = {
  void: VoidNode,
};

const edgeTypes = {
  void: AtomieEdge,
};

const getLayoutedElements = (nodes: Node[], edges: Edge[]) => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  // Increase spacing to prevent overlaps
  dagreGraph.setGraph({ rankdir: "LR", nodesep: 80, ranksep: 200 });

  const connectedNodeIds = new Set<string>();
  edges.forEach((e) => {
    connectedNodeIds.add(e.source);
    connectedNodeIds.add(e.target);
  });

  const connectedNodes = nodes.filter((n) => connectedNodeIds.has(n.id));
  const isolatedNodes = nodes.filter((n) => !connectedNodeIds.has(n.id));

  connectedNodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 380, height: 100 });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  let maxX = 0;
  let maxY = 0;

  const layoutedConnected = connectedNodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    const x = nodeWithPosition.x - 380 / 2;
    const y = nodeWithPosition.y - 100 / 2;
    maxX = Math.max(maxX, x + 380);
    maxY = Math.max(maxY, y + 100);
    return {
      ...node,
      position: { x, y },
    };
  });

  // Display isolated nodes in a grid below the main DAG to prevent a giant vertical column collapse
  // Force a reasonable maximum width of columns so fitView doesn't zoom out microscopically
  const COLUMNS = Math.min(3, Math.max(1, Math.ceil(Math.sqrt(isolatedNodes.length))));
  const GRID_X_START = 0;
  const GRID_Y_START = connectedNodes.length > 0 ? maxY + 120 : 0;
  const NODE_WIDTH = 380;
  const NODE_HEIGHT = 100;
  const SPACING_X = 60;
  const SPACING_Y = 60;

  const layoutedIsolated = isolatedNodes.map((node, index) => {
    const col = index % COLUMNS;
    const row = Math.floor(index / COLUMNS);
    return {
      ...node,
      position: {
        x: GRID_X_START + col * (NODE_WIDTH + SPACING_X),
        y: GRID_Y_START + row * (NODE_HEIGHT + SPACING_Y),
      },
    };
  });

  return { nodes: [...layoutedConnected, ...layoutedIsolated], edges };
};

export function OpenApiGraph() {
  const { data, isLoading, error } = useGraph();
  const { graphClusterFilter, selectedWorkflowId, setGraphClusterFilter } = useReviewStore();
  const [selectedNodeData, setSelectedNodeData] = useState<GraphNode | GraphCommunity | null>(null);
  const [isLeftSidebarOpen, setIsLeftSidebarOpen] = useState(true);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(true);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [rfInstance, setRfInstance] = useState<ReactFlowInstance | null>(null);

  useEffect(() => {
    if (!data) return;

    let initialNodes: Node[] = [];
    let initialEdges: Edge[] = [];

    if (!graphClusterFilter) {
      initialNodes = data.communities.map((comm) => ({
        id: `comm-${comm.id}`,
        type: "void",
        position: { x: 0, y: 0 },
        data: {
          label: comm.workflowName,
          isCommunityNode: true,
          communitySize: comm.size,
          rawCommunity: comm,
        },
      }));

      const commEdges = new Set<string>();
      data.edges.forEach((e) => {
        const sourceNode = data.nodes.find(n => n.id === e.source);
        const targetNode = data.nodes.find(n => n.id === e.target);
        if (sourceNode && targetNode && sourceNode.communityId !== targetNode.communityId) {
          const edgeId = `comm-${sourceNode.communityId}->comm-${targetNode.communityId}`;
          if (!commEdges.has(edgeId)) {
            commEdges.add(edgeId);
            initialEdges.push({
              id: edgeId,
              source: `comm-${sourceNode.communityId}`,
              target: `comm-${targetNode.communityId}`,
              type: "void",
              animated: true,
              markerEnd: {
                type: MarkerType.ArrowClosed,
                width: 15,
                height: 15,
                color: '#94a3b8',
              },
            });
          }
        }
      });
    } else {
      const filteredEndpoints = data.nodes.filter(n => n.communityId === graphClusterFilter);
      const visibleIds = new Set(filteredEndpoints.map(n => n.id));
      
      initialNodes = filteredEndpoints.map((n) => ({
        id: n.id,
        type: "void",
        position: { x: 0, y: 0 },
        data: {
          label: n.label,
          method: n.method,
          rawNode: n,
        },
      }));

      const edgeMap = new Map<string, Edge>();
      data.edges
        .filter(e => visibleIds.has(e.source) && visibleIds.has(e.target))
        .forEach(e => {
          const edgeId = `${e.source}-${e.target}`;
          if (!edgeMap.has(edgeId)) {
            edgeMap.set(edgeId, {
              id: edgeId,
              source: e.source,
              target: e.target,
              type: "void",
              label: (e as any).type || "Calls",
              markerEnd: {
                type: MarkerType.ArrowClosed,
                width: 15,
                height: 15,
                color: '#cbd5e1',
              },
            });
          } else {
             const existing = edgeMap.get(edgeId)!;
             const newLabel = (e as any).type || "Calls";
             if (existing.label && !String(existing.label).includes(newLabel)) {
                existing.label = `${existing.label}, ${newLabel}`;
             }
          }
        });
      initialEdges = Array.from(edgeMap.values());
    }

    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(initialNodes, initialEdges);
    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
    setSelectedNodeData(null);
    
    if (rfInstance) {
      setTimeout(() => {
        rfInstance.fitView({ padding: 0.4, duration: 800, maxZoom: 1, minZoom: 0.65 });
      }, 50);
    }
  }, [data, graphClusterFilter, rfInstance]);

  const onNodeClick = (_: React.MouseEvent, node: Node) => {
    setNodes((nds) => nds.map((n) => ({ ...n, selected: n.id === node.id })));
    if (node.data.isCommunityNode) {
      const comm = node.data.rawCommunity as GraphCommunity;
      setSelectedNodeData(comm);
      setGraphClusterFilter(comm.id);
    } else {
      setSelectedNodeData(node.data.rawNode as GraphNode);
    }
  };

  const onPaneClick = () => {
    setSelectedNodeData(null);
    setNodes((nds) => nds.map((n) => ({ ...n, selected: false })));
  };

  if (error) return <ErrorState message={(error as Error).message} />;
  if (isLoading) return <Skeleton className="h-[620px] w-full bg-gray-50" />;
  if (!data?.nodes.length) {
    return <EmptyState title="No graph data available" description="Endpoints will appear after backend processing." />;
  }

  const isCommunityView = !graphClusterFilter;

  return (
    <div className="mcp-sandbox h-[750px] w-full flex border border-gray-200 rounded-md overflow-hidden text-gray-900">
      
      {/* Pane 1: Left Sidebar (Tree View) */}
      <div className={`flex-shrink-0 bg-white border-r border-gray-200 flex flex-col transition-all duration-300 ${isLeftSidebarOpen ? 'w-[260px]' : 'w-0 border-r-0 hidden'}`}>
        <div className="p-4 border-b border-gray-200 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <TreeStructure size={20} weight="duotone" className="text-gray-500" />
            <h2 className="text-sm font-semibold tracking-wide">Ingested APIs</h2>
          </div>
          <button onClick={() => setIsLeftSidebarOpen(false)} className="text-gray-400 hover:text-gray-700">
             <CaretLeft size={16} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-1 custom-scrollbar">
          {data.communities.map(comm => (
            <div key={comm.id} className="group">
              <button 
                onClick={() => {
                  if (graphClusterFilter === comm.id) {
                    setGraphClusterFilter(null);
                  } else {
                    setGraphClusterFilter(comm.id);
                    setSelectedNodeData(comm);
                  }
                }}
                className={`w-full flex items-center gap-2 px-2 py-2 text-left text-sm transition-colors ${
                  graphClusterFilter === comm.id ? "bg-blue-50 text-blue-600" : "text-gray-500 hover:text-gray-900"
                }`}
              >
                <CaretRight size={14} className={graphClusterFilter === comm.id ? "rotate-90" : ""} />
                <span className="truncate">{comm.workflowName}</span>
              </button>
              {graphClusterFilter === comm.id && (
                <div className="ml-5 mt-1 space-y-1 border-l border-gray-200 pl-2">
                  {data.nodes.filter(n => n.communityId === comm.id).map(n => (
                    <button 
                      key={n.id} 
                      onClick={() => {
                        setNodes((nds) => nds.map((node) => ({ ...node, selected: node.id === n.id })));
                        setSelectedNodeData(n);
                        
                        if (rfInstance) {
                          const rfNode = rfInstance.getNode(n.id);
                          if (rfNode) {
                            const { x, y } = rfNode.position;
                            rfInstance.setCenter(x + 190, y + 50, { zoom: 1, duration: 800 });
                          }
                        }
                      }}
                      className={`w-full flex items-center text-left gap-2 px-2 py-1.5 text-sm transition-colors cursor-pointer ${
                        selectedNodeData && "id" in selectedNodeData && selectedNodeData.id === n.id ? "bg-gray-100 text-gray-900 font-semibold border-l-2 border-blue-500 -ml-[2px]" : "text-gray-500 hover:text-gray-900"
                      }`}
                    >
                      <ListDashes size={12} weight="duotone" className="shrink-0" />
                      <span className="truncate">{n.label}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Pane 2: Central Canvas */}
      <div className="flex-1 relative bg-gray-50 h-full w-full">
        {/* Top left overlay for canvas context & Sidebar Toggles */}
        <div className="absolute top-4 left-4 z-10 flex gap-2 items-center">
          {!isLeftSidebarOpen && (
            <button 
               onClick={() => setIsLeftSidebarOpen(true)}
               className="bg-white border border-gray-200 p-2 rounded-sm shadow-md hover:bg-gray-50 text-gray-500 hover:text-gray-800 transition-colors"
               title="Open Ingested APIs"
            >
              <SidebarSimple size={16} />
            </button>
          )}
          <div className="bg-white border border-gray-200 px-3 py-1.5 rounded-sm flex items-center gap-2 shadow-xl">
          {isCommunityView ? (
             <span className="text-xs text-gray-500">GLOBAL / CLUSTER TOPOLOGY</span>
          ) : (
            <div className="flex items-center gap-2">
              <button onClick={() => setGraphClusterFilter(null)} className="text-gray-500 hover:text-gray-900 text-xs">
                 [ BACK ]
              </button>
              <span className="text-xs text-blue-600">/ {graphClusterFilter}</span>
            </div>
          )}
          </div>
        </div>

        {/* Top right overlay for Right Sidebar Toggle */}
        <div className="absolute top-4 right-4 z-10 flex gap-2 items-center">
          {!isRightSidebarOpen && (
            <button 
               onClick={() => setIsRightSidebarOpen(true)}
               className="bg-white border border-gray-200 p-2 rounded-sm shadow-md hover:bg-gray-50 text-gray-500 hover:text-gray-800 transition-colors"
               title="Open Context Budget Inspector"
            >
              <SidebarSimple size={16} />
            </button>
          )}
        </div>

        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          onInit={setRfInstance}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          fitViewOptions={{ padding: 0.4, maxZoom: 1, minZoom: 0.65 }}
          minZoom={0.1}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#E2E8F0" gap={20} size={2} />
          <Controls className="bg-white border border-gray-200 fill-gray-500 shadow-xl" />
        </ReactFlow>
      </div>

      {/* Pane 3: Context Budget Inspector */}
      <div className={`flex-shrink-0 bg-white border-l border-gray-200 flex flex-col transition-all duration-300 ${isRightSidebarOpen ? 'w-[320px]' : 'w-0 border-l-0 hidden'}`}>
         <div className="p-4 border-b border-gray-200 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <TerminalWindow size={20} weight="duotone" className="text-blue-600" />
            <h2 className="text-sm font-semibold tracking-wide">Context Inspector</h2>
          </div>
          <button onClick={() => setIsRightSidebarOpen(false)} className="text-gray-400 hover:text-gray-700">
             <CaretRight size={16} />
          </button>
        </div>
        
        <div className="flex-1 p-4 overflow-y-auto space-y-6">
          {!selectedNodeData ? (
             <div className="flex flex-col items-center justify-center h-full text-gray-500 space-y-3 opacity-50">
               <Desktop size={48} weight="duotone" />
               <p className="text-xs">NO_TARGET_ACQUIRED</p>
             </div>
          ) : (
            <>
              {/* Target Identity */}
              <div className="space-y-2">
                 <div className="text-[10px] text-blue-600 uppercase tracking-widest font-semibold">Target Identity</div>
                 <div className="p-3 bg-gray-50 border border-gray-200 rounded-sm text-xs break-all">
                    {"workflowName" in selectedNodeData ? selectedNodeData.workflowName : selectedNodeData.label}
                 </div>
              </div>

              {/* Resource Metrics */}
              <div className="space-y-2">
                 <div className="text-[10px] text-gray-500 uppercase tracking-widest font-semibold">Resource Footprint</div>
                 <div className="grid grid-cols-2 gap-2">
                   <div className="p-3 bg-gray-50 border border-gray-200 rounded-sm flex flex-col gap-1">
                      <div className="text-[10px] text-gray-500 flex items-center gap-1"><Coins size={12}/> Tokens</div>
                      <div className="text-sm text-gray-900 font-medium">
                        {"workflowName" in selectedNodeData ? (selectedNodeData.size * 142) : Math.floor(Math.random() * 500 + 100)}
                      </div>
                   </div>
                   <div className="p-3 bg-gray-50 border border-gray-200 rounded-sm flex flex-col gap-1">
                      <div className="text-[10px] text-gray-500 flex items-center gap-1"><Graph size={12}/> Weight</div>
                      <div className="text-sm text-gray-900 font-medium">
                        {"workflowName" in selectedNodeData ? `${selectedNodeData.size} Nodes` : 'O(1)'}
                      </div>
                   </div>
                 </div>
              </div>

              {/* Console Output Mock */}
              <div className="space-y-2 pt-4">
                 <div className="text-[10px] text-gray-500 uppercase tracking-widest font-semibold">Inspector Log</div>
                 <div className="p-3 bg-gray-100 border border-gray-200 rounded-sm text-[10px] text-gray-800 leading-relaxed opacity-80 h-32 overflow-y-auto">
                    {`> INIT_INSPECTOR()\n`}
                    {`> TARGET_ID: ${selectedNodeData.id}\n`}
                    {"workflowName" in selectedNodeData ? 
                      `> RESOLVING_CLUSTER...\n> FOUND ${selectedNodeData.size} ENDPOINTS\n> CALCULATING_BUDGET...\n> STATUS: OK` : 
                      `> METHOD: ${selectedNodeData.method}\n> COMMUNITY_BINDING: ${selectedNodeData.communityId}\n> ESTIMATING_TOKENS...\n> STATUS: OK`}
                 </div>
              </div>
            </>
          )}
        </div>
      </div>

    </div>
  );
}
