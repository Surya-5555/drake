import type { Metadata } from "next";
import type { ReactNode } from "react";

import "@/app/globals.css";
import { Providers } from "@/components/providers";
import { Sidebar } from "@/components/shell/sidebar";
import { Topbar } from "@/components/shell/topbar";

export const metadata: Metadata = {
  title: "Dell MCP Proxy Governance",
  description: "Human-in-the-loop workflow governance and observability",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="flex h-screen bg-gradient-to-br from-black to-[#2a3c1f] p-4 md:p-8 overflow-hidden">
            <div className="flex flex-1 overflow-hidden bg-[rgb(var(--background))] rounded-3xl shadow-2xl">
              <Sidebar />
              <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
                <Topbar />
                <main className="flex-1 p-6 lg:p-10 relative">
                  {children}
                </main>
              </div>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
