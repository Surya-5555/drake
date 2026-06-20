"use client";

import { Play, RefreshCw, User } from "lucide-react";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { useOverview } from "@/hooks/use-overview";

export function Topbar() {
  const pathname = usePathname();
  const { isFetching, refetch } = useOverview();

  // Create a simple breadcrumb from pathname
  const pageName = pathname === "/" ? "Overview" : pathname.substring(1).charAt(0).toUpperCase() + pathname.substring(2);

  return (
    <header className="flex min-h-16 items-center justify-between px-8 py-4 bg-[rgb(var(--card))] rounded-tr-3xl border-b border-[rgb(var(--border))]">
      <div className="flex items-center gap-3">
        <h2 className="text-sm font-bold text-[rgb(var(--foreground))]">{pageName}</h2>
        <span className="text-xs text-[rgb(var(--muted-foreground))]">&bull;</span>
        <span className="text-xs text-[rgb(var(--muted-foreground))]">Updated just now</span>
      </div>
      
      <div className="flex items-center gap-4">
        {/* Mock Avatars */}
        <div className="flex -space-x-2 mr-2">
          <div className="w-6 h-6 rounded-full bg-gray-200 border-2 border-white flex items-center justify-center overflow-hidden"><User className="w-3 h-3 text-gray-500" /></div>
          <div className="w-6 h-6 rounded-full bg-blue-200 border-2 border-white flex items-center justify-center overflow-hidden"><User className="w-3 h-3 text-blue-500" /></div>
        </div>

        <Button
          aria-label="Refresh overview data"
          disabled={isFetching}
          onClick={() => refetch()}
          size="sm"
          variant="secondary"
          className="rounded-full bg-gray-100 hover:bg-gray-200 text-gray-600 border-none shadow-none font-semibold text-xs"
        >
          <RefreshCw className={isFetching ? "mr-2 h-3 w-3 animate-spin" : "mr-2 h-3 w-3"} />
          Refresh
        </Button>
        
        <Button
          size="sm"
          variant="secondary"
          className="rounded-full bg-gray-100 hover:bg-gray-200 text-gray-600 border-none shadow-none font-semibold text-xs"
        >
          <Play className="mr-2 h-3 w-3" />
          Run Once
        </Button>
        
        <Button
          size="sm"
          className="rounded-full bg-[rgb(var(--primary))] hover:bg-[#a5cc5f] text-black font-semibold text-xs shadow-sm border-none"
        >
          Publish
        </Button>
      </div>
    </header>
  );
}
