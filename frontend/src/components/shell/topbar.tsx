"use client";

import { Menu, RefreshCw, ShieldCheck, ShieldOff, X } from "lucide-react";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { NavLinks } from "@/components/shell/nav-items";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useOverview } from "@/hooks/use-overview";
import type { PipelineStatus } from "@/lib/types";

function runtimeTone(status?: PipelineStatus): "success" | "warning" | "danger" | "neutral" {
  switch (status) {
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

function runtimeLabel(status?: PipelineStatus) {
  switch (status) {
    case "complete":
      return "MCP runtime online";
    case "running":
      return "MCP runtime starting";
    case "error":
      return "MCP runtime error";
    case "idle":
      return "MCP runtime idle";
    default:
      return "MCP runtime unknown";
  }
}

export function Topbar() {
  const pathname = usePathname();
  const { data, isFetching, refetch } = useOverview();
  const [mobileOpen, setMobileOpen] = useState(false);
  const tone = runtimeTone(data?.mcpRuntimeStatus);

  return (
    <>
      <header className="flex min-h-16 flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 lg:px-6">
        <div className="flex min-w-0 items-start gap-3">
          <Button
            aria-expanded={mobileOpen}
            aria-label="Open navigation menu"
            className="lg:hidden"
            onClick={() => setMobileOpen(true)}
            size="icon"
            variant="secondary"
          >
            <Menu className="h-4 w-4" />
          </Button>
          <div className="min-w-0">
            <h1 className="text-lg font-semibold text-slate-950">
              Enterprise MCP Workflow Proxy
            </h1>
            <p className="text-sm text-slate-500">
              Human-in-the-loop workflow governance and observability
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            aria-label="Refresh overview data"
            disabled={isFetching}
            onClick={() => refetch()}
            size="sm"
            variant="secondary"
          >
            <RefreshCw className={isFetching ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Refresh
          </Button>
          <Badge className="hidden sm:inline-flex" tone={tone}>
            {tone === "success" ? (
              <ShieldCheck className="mr-1 h-3.5 w-3.5" />
            ) : (
              <ShieldOff className="mr-1 h-3.5 w-3.5" />
            )}
            {runtimeLabel(data?.mcpRuntimeStatus)}
          </Badge>
        </div>
      </header>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            aria-label="Close navigation menu"
            className="absolute inset-0 bg-slate-950/30"
            onClick={() => setMobileOpen(false)}
            type="button"
          />
          <aside className="relative flex h-full w-72 flex-col bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
              <div>
                <div className="text-sm font-semibold text-slate-900">Dell MCP Proxy</div>
                <div className="text-xs text-slate-500">Governance Console</div>
              </div>
              <Button
                aria-label="Close menu"
                onClick={() => setMobileOpen(false)}
                size="icon"
                variant="ghost"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            <NavLinks
              className="p-3"
              onNavigate={() => setMobileOpen(false)}
              pathname={pathname}
            />
          </aside>
        </div>
      ) : null}
    </>
  );
}
