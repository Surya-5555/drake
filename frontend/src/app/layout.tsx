import type { Metadata } from "next";
import type { ReactNode } from "react";

import "@/app/globals.css";
import { Providers } from "@/components/providers";
import { Sidebar } from "@/components/shell/sidebar";
import { Topbar } from "@/components/shell/topbar";

export const metadata: Metadata = {
  title: "Dell MCP Governance Console",
  description: "Governance and observability UI for workflow-oriented MCP tools.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="flex min-h-screen bg-slate-50">
            <Sidebar />
            <div className="min-w-0 flex-1">
              <Topbar />
              <main className="mx-auto w-full max-w-7xl px-4 py-5 lg:px-6">
                {children}
              </main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}

