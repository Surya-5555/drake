"use client";

import {
  Activity,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  ScrollText,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { isActiveRoute, navItems } from "@/components/shell/nav-items";
import { cn } from "@/lib/utils";

const navIcons = {
  "/": LayoutDashboard,
  "/workflows": ListChecks,
  "/graph": GitBranch,
  "/metrics": Activity,
  "/audit": ScrollText,
} as const;

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-64 shrink-0 border-r border-slate-200 bg-white lg:block">
      <div className="border-b border-slate-200 px-5 py-4">
        <div className="text-sm font-semibold text-slate-900">Dell MCP Proxy</div>
        <div className="text-xs text-slate-500">Governance Console</div>
      </div>
      <nav aria-label="Primary navigation" className="space-y-1 p-3">
        {navItems.map((item) => {
          const active = isActiveRoute(pathname, item.href);
          const Icon = navIcons[item.href];
          return (
            <Link
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-sky-50 text-sky-900"
                  : "text-slate-700 hover:bg-slate-100",
              )}
              href={item.href}
              key={item.href}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
