import { Handle, Position } from "@xyflow/react";
import * as React from "react";

import {
  AtomieBubbleIcon,
  AtomieDatabaseIcon,
  AtomieDeleteIcon,
  AtomieMoreIcon,
  AtomieSparkleIcon,
} from "./custom-icons";

export function AtomieNode({ data, selected }: any) {
  const { label, method, communityColor, isCommunityNode, communitySize } = data;

  // Determine icon based on HTTP method or type
  let Icon = AtomieBubbleIcon;
  let bgClass = "bg-blue-100 text-blue-600";

  if (isCommunityNode) {
    Icon = AtomieSparkleIcon;
    bgClass = "bg-[#BDE56C] text-[#2c4000]";
  } else {
    switch (method) {
      case "GET":
        Icon = AtomieDatabaseIcon;
        bgClass = "bg-amber-100 text-amber-600";
        break;
      case "POST":
        Icon = AtomieSparkleIcon;
        bgClass = "bg-[#BDE56C] text-[#2c4000]";
        break;
      case "PUT":
      case "PATCH":
        Icon = AtomieBubbleIcon;
        bgClass = "bg-indigo-100 text-indigo-600";
        break;
      case "DELETE":
        Icon = AtomieDeleteIcon;
        bgClass = "bg-red-100 text-red-600";
        break;
    }
  }

  return (
    <div
      className={`relative flex items-center justify-between min-w-[240px] px-2 py-2 rounded-full bg-white shadow-[0_4px_12px_rgba(0,0,0,0.05)] border-2 transition-all ${
        selected ? "border-[#A5D64C] shadow-[#A5D64C]/20" : "border-gray-100"
      }`}
    >
      <Handle type="target" position={Position.Top} className="opacity-0 w-4 h-4 bg-transparent -mt-2" />

      <div className="flex items-center gap-3 w-full">
        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${bgClass}`}>
          <Icon className="w-5 h-5" />
        </div>
        
        <div className="flex flex-col flex-1 truncate pr-2">
          <span className="text-sm font-semibold text-gray-800 truncate">
            {isCommunityNode ? `Cluster ${label}` : label}
          </span>
          <span className="text-[10px] text-gray-400 font-medium tracking-wide">
            {isCommunityNode ? `${communitySize} Endpoints` : `${method} Request`}
          </span>
        </div>

        <button className="w-8 h-8 rounded-full hover:bg-gray-100 flex items-center justify-center text-gray-400 transition-colors shrink-0">
          <AtomieMoreIcon className="w-4 h-4" />
        </button>
      </div>

      <Handle type="source" position={Position.Bottom} className="opacity-0 w-4 h-4 bg-transparent -mb-2" />
    </div>
  );
}
