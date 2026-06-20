import { Handle, Position } from "@xyflow/react";
import * as React from "react";
import {
  Database,
  TerminalWindow,
  Graph,
  Network,
  Lightning,
  DotsThreeCircle,
  Cube,
  FolderOpen
} from "@phosphor-icons/react";

export function VoidNode({ data, selected }: any) {
  const { label, method, isCommunityNode, communitySize } = data;

  let Icon = TerminalWindow;
  let iconColor = "text-gray-500";
  let leftBarColor = "bg-gray-300";
  let badgeBg = "bg-gray-100";
  let badgeText = "text-gray-600";

  if (isCommunityNode) {
    Icon = FolderOpen;
    iconColor = "text-indigo-500";
    leftBarColor = "bg-indigo-500";
    badgeBg = "bg-indigo-50";
    badgeText = "text-indigo-700";
  } else {
    switch (method) {
      case "GET":
        Icon = Database;
        iconColor = "text-blue-500";
        leftBarColor = "bg-blue-500";
        badgeBg = "bg-blue-50";
        badgeText = "text-blue-700";
        break;
      case "POST":
        Icon = Lightning;
        iconColor = "text-emerald-500";
        leftBarColor = "bg-emerald-500";
        badgeBg = "bg-emerald-50";
        badgeText = "text-emerald-700";
        break;
      case "PUT":
      case "PATCH":
        Icon = Cube;
        iconColor = "text-amber-500";
        leftBarColor = "bg-amber-500";
        badgeBg = "bg-amber-50";
        badgeText = "text-amber-700";
        break;
      case "DELETE":
        Icon = Network; // Abstract
        iconColor = "text-rose-500";
        leftBarColor = "bg-rose-500";
        badgeBg = "bg-rose-50";
        badgeText = "text-rose-700";
        break;
    }
  }

  return (
    <div
      className={`relative flex items-center justify-between w-[380px] h-[100px] p-4 bg-white border transition-all rounded-lg shadow-sm ${
        selected ? "border-blue-500 ring-2 ring-blue-500 shadow-md" : "border-gray-200 hover:border-gray-300 hover:shadow"
      }`}
    >
      {/* Left color bar indicator */}
      <div className={`absolute left-0 top-0 bottom-0 w-1.5 ${leftBarColor} rounded-l-lg`} />

      <Handle 
        type="target" 
        position={Position.Left} 
        className={`w-4 h-4 rounded-full border-2 border-white ${leftBarColor} -ml-2`} 
      />

      <div className="flex items-center gap-4 w-full pl-3">
        <div className={`flex items-center justify-center w-12 h-12 rounded-xl bg-gray-50 border border-gray-100 shrink-0 ${iconColor}`}>
          <Icon size={28} weight="duotone" />
        </div>
        
        <div className="flex flex-col flex-1 min-w-0 pr-2">
          <div className="flex items-center gap-2 mb-1.5">
            <span className={`text-xs font-bold px-2 py-0.5 rounded-md ${badgeBg} ${badgeText} tracking-wider`}>
              {isCommunityNode ? "CLUSTER" : method}
            </span>
            {isCommunityNode && (
              <span className="text-xs text-gray-500 font-medium tracking-wide">
                {communitySize} NODES
              </span>
            )}
          </div>
          <span className="text-base font-bold text-gray-900 tracking-tight truncate block w-full" title={label}>
            {label}
          </span>
        </div>

        <button className="flex items-center justify-center text-gray-400 hover:text-gray-700 transition-colors shrink-0">
          <DotsThreeCircle size={28} weight="regular" />
        </button>
      </div>

      <Handle 
        type="source" 
        position={Position.Right} 
        className={`w-4 h-4 rounded-full border-2 border-white ${leftBarColor} -mr-2`} 
      />
    </div>
  );
}
