"use client";

import { useMemo, useState } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuditEvents } from "@/hooks/use-audit";
import type { AuditEvent } from "@/lib/types";

const eventTypes = [
  "all",
  "workflow_generated",
  "workflow_reviewed",
  "workflow_approved",
  "workflow_rejected",
  "workflow_updated",
  "mcp_registered",
] as const;

function matchesSearch(event: AuditEvent, query: string) {
  const haystack = [
    event.eventType,
    event.status,
    event.workflowName,
    event.description,
    event.actor,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(query.toLowerCase());
}

export function AuditTrail() {
  const { data, isLoading, error } = useAuditEvents();
  const [eventFilter, setEventFilter] = useState<(typeof eventTypes)[number]>("all");
  const [search, setSearch] = useState("");

  const filteredEvents = useMemo(() => {
    if (!data) return [];
    return data.filter((event) => {
      const matchesType =
        eventFilter === "all" ||
        event.eventType.toLowerCase() === eventFilter.replaceAll("_", " ") ||
        event.eventType.toLowerCase() === eventFilter ||
        event.eventType.toLowerCase().includes(eventFilter.replaceAll("_", " "));
      const matchesQuery = !search.trim() || matchesSearch(event, search.trim());
      return matchesType && matchesQuery;
    });
  }, [data, eventFilter, search]);

  if (error) {
    return <ErrorState message={(error as Error).message} />;
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton className="h-20" key={index} />
        ))}
      </div>
    );
  }

  if (!data?.length) {
    return (
      <EmptyState
        title="No audit events"
        description="Workflow generation, review, approval, and MCP registration events will be listed here."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Input
          aria-label="Search audit events"
          className="max-w-md"
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by workflow, actor, or description"
          value={search}
        />
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <span className="whitespace-nowrap">Event type</span>
          <select
            className="h-9 rounded-md border border-slate-300 bg-white px-2 text-sm"
            onChange={(event) =>
              setEventFilter(event.target.value as (typeof eventTypes)[number])
            }
            value={eventFilter}
          >
            {eventTypes.map((type) => (
              <option key={type} value={type}>
                {type === "all" ? "All events" : type.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        </label>
      </div>

      {!filteredEvents.length ? (
        <EmptyState
          title="No matching audit events"
          description="Adjust the search query or event filter to view lifecycle records."
        />
      ) : (
        <div className="space-y-3">
          {filteredEvents.map((event) => (
            <Card className="p-4" key={event.id}>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-sm font-semibold text-slate-950">
                      {event.eventType}
                    </h3>
                    <Badge tone="neutral">{event.status}</Badge>
                    {event.workflowName ? (
                      <Badge tone="default">{event.workflowName}</Badge>
                    ) : null}
                  </div>
                  <p className="mt-2 text-sm text-slate-600">{event.description}</p>
                  <p className="mt-2 text-xs text-slate-500">Actor: {event.actor}</p>
                </div>
                <time className="text-xs text-slate-500" dateTime={event.timestamp}>
                  {new Intl.DateTimeFormat(undefined, {
                    dateStyle: "medium",
                    timeStyle: "short",
                  }).format(new Date(event.timestamp))}
                </time>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
