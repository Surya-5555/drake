"use client";

import {
  Activity,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  ScrollText,
  Settings,
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
};

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-64 shrink-0 bg-white lg:flex flex-col border-r border-[rgb(var(--border))] rounded-l-3xl">
      <div className="px-8 py-10">
        <h1 className="text-xl font-bold text-[rgb(var(--foreground))] flex items-center gap-3">
          <div className="w-5 h-5 bg-[rgb(var(--primary))] rounded-[4px] rotate-45 shadow-[2px_2px_10px_rgba(189,229,108,0.5)]"></div>
          Atomie<span className="text-[10px] align-top text-gray-400 font-normal mt-1">TM</span>
        </h1>
      </div>
      <nav aria-label="Primary navigation" className="space-y-1.5 px-4 flex-1">
        {navItems.map((item) => {
          const active = isActiveRoute(pathname, item.href);
          const Icon = navIcons[item.href as keyof typeof navIcons];
          return (
            <Link
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-4 rounded-xl px-4 py-3 text-[14px] font-medium transition-all mb-1",
                active
                  ? "bg-[rgb(var(--primary))] text-[rgb(var(--foreground))] shadow-sm"
                  : "text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] hover:bg-gray-50",
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
      <div className="p-4 mt-auto">
        <div className="flex items-center gap-3 text-sm text-[rgb(var(--muted-foreground))] px-4 py-3 hover:bg-gray-50 rounded-xl cursor-pointer transition-colors">
          <Settings className="w-4 h-4" />
          Settings
        </div>
      </div>
    </aside>
  );
}
