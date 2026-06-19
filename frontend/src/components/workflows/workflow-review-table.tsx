"use client";

import { Check, GitBranch, Pencil, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  useApproveWorkflow,
  usePendingWorkflows,
  useRejectWorkflow,
  useUpdateWorkflow,
} from "@/hooks/use-workflows";
import type { RiskLevel, WorkflowCluster } from "@/lib/types";
import { useReviewStore } from "@/store/review-store";

const riskTone: Record<RiskLevel, "success" | "warning" | "danger" | "neutral"> = {
  low: "success",
  medium: "warning",
  high: "danger",
  critical: "danger",
};

type ActionFeedback = {
  type: "success" | "error";
  message: string;
};

function EditWorkflowDialog({
  workflow,
  open,
  onOpenChange,
  onSaved,
}: {
  workflow: WorkflowCluster | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (message: string) => void;
}) {
  const updateWorkflow = useUpdateWorkflow();
  const [workflowName, setWorkflowName] = useState("");
  const [generatedDescription, setGeneratedDescription] = useState("");

  useEffect(() => {
    if (workflow) {
      setWorkflowName(workflow.workflowName);
      setGeneratedDescription(workflow.generatedDescription);
    }
  }, [workflow]);

  const handleSave = () => {
    if (!workflow) return;

    updateWorkflow.mutate(
      {
        workflowId: workflow.id,
        payload: { workflowName, generatedDescription },
      },
      {
        onSuccess: () => {
          onOpenChange(false);
          onSaved(`Updated workflow label for "${workflowName}".`);
        },
        onError: (error) => {
          onSaved((error as Error).message);
        },
      },
    );
  };

  return (
    <Dialog onOpenChange={onOpenChange} open={open}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit workflow label</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 p-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="edit-workflow-name">
              Workflow name
            </label>
            <Input
              id="edit-workflow-name"
              onChange={(event) => setWorkflowName(event.target.value)}
              value={workflowName}
            />
          </div>
          <div>
            <label
              className="mb-1 block text-xs font-medium text-slate-600"
              htmlFor="edit-workflow-description"
            >
              Generated description
            </label>
            <Textarea
              id="edit-workflow-description"
              onChange={(event) => setGeneratedDescription(event.target.value)}
              rows={4}
              value={generatedDescription}
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button onClick={() => onOpenChange(false)} variant="secondary">
              Cancel
            </Button>
            <Button disabled={updateWorkflow.isPending} onClick={handleSave}>
              Save changes
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function RejectWorkflowDialog({
  workflow,
  open,
  onOpenChange,
  onRejected,
}: {
  workflow: WorkflowCluster | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRejected: (message: string, isError?: boolean) => void;
}) {
  const rejectWorkflow = useRejectWorkflow();
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (workflow) {
      setReason("");
    }
  }, [workflow]);

  const handleReject = () => {
    if (!workflow || !reason.trim()) return;

    rejectWorkflow.mutate(
      { workflowId: workflow.id, reason: reason.trim() },
      {
        onSuccess: () => {
          onOpenChange(false);
          onRejected(`Rejected workflow "${workflow.workflowName}".`);
        },
        onError: (error) => {
          onRejected((error as Error).message, true);
        },
      },
    );
  };

  return (
    <Dialog onOpenChange={onOpenChange} open={open}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reject workflow cluster</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 p-4">
          <p className="text-sm text-slate-600">
            Provide a governance reason for rejecting{" "}
            <span className="font-medium text-slate-900">{workflow?.workflowName}</span>.
            This event will be recorded in the audit trail.
          </p>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600" htmlFor="reject-reason">
              Rejection reason
            </label>
            <Textarea
              id="reject-reason"
              onChange={(event) => setReason(event.target.value)}
              placeholder="Describe why this cluster should not be registered as an MCP tool."
              rows={4}
              value={reason}
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button onClick={() => onOpenChange(false)} variant="secondary">
              Cancel
            </Button>
            <Button
              disabled={rejectWorkflow.isPending || !reason.trim()}
              onClick={handleReject}
              variant="destructive"
            >
              Confirm rejection
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function WorkflowReviewTable() {
  const { data, isLoading, error } = usePendingWorkflows();
  const approveWorkflow = useApproveWorkflow();
  const setGraphClusterFilter = useReviewStore((state) => state.setGraphClusterFilter);
  const setSelectedWorkflowId = useReviewStore((state) => state.setSelectedWorkflowId);

  const [editing, setEditing] = useState<WorkflowCluster | null>(null);
  const [rejecting, setRejecting] = useState<WorkflowCluster | null>(null);
  const [feedback, setFeedback] = useState<ActionFeedback | null>(null);

  useEffect(() => {
    if (!feedback) return;
    const timer = window.setTimeout(() => setFeedback(null), 5000);
    return () => window.clearTimeout(timer);
  }, [feedback]);

  const handleApprove = (workflow: WorkflowCluster) => {
    approveWorkflow.mutate(workflow.id, {
      onSuccess: () => {
        setFeedback({
          type: "success",
          message: `Approved "${workflow.workflowName}" and triggered FastMCP reload.`,
        });
      },
      onError: (mutationError) => {
        setFeedback({
          type: "error",
          message: (mutationError as Error).message,
        });
      },
    });
  };

  const handleViewInGraph = (workflow: WorkflowCluster) => {
    const clusterId = workflow.communityId ?? workflow.id;
    setSelectedWorkflowId(workflow.id);
    setGraphClusterFilter(clusterId);
  };

  if (error) {
    return <ErrorState message={(error as Error).message} />;
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton className="h-28 w-full" key={index} />
        ))}
      </div>
    );
  }

  if (!data?.length) {
    return (
      <EmptyState
        title="No pending workflow clusters"
        description="Pending clusters will appear here after graph construction and local semantic labeling complete."
      />
    );
  }

  return (
    <div className="space-y-3">
      {feedback ? (
        <div
          aria-live="polite"
          className={
            feedback.type === "success"
              ? "rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800"
              : "rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800"
          }
          role="status"
        >
          {feedback.message}
        </div>
      ) : null}

      {data.map((workflow) => (
        <Card className="p-4" key={workflow.id}>
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-base font-semibold text-slate-950">
                  {workflow.workflowName}
                </h3>
                <Badge tone={riskTone[workflow.riskLevel]}>
                  {workflow.riskLevel} risk
                </Badge>
                <Badge tone="neutral">{workflow.clusterSize} endpoints</Badge>
                <Badge tone="default">
                  {Math.round(workflow.confidence * 100)}% confidence
                </Badge>
              </div>
              <p className="mt-2 text-sm text-slate-600">
                {workflow.generatedDescription}
              </p>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-sm">
                  <caption className="sr-only">
                    Underlying endpoints for {workflow.workflowName}
                  </caption>
                  <thead className="text-xs uppercase text-slate-500">
                    <tr>
                      <th className="py-2 pr-3" scope="col">
                        Method
                      </th>
                      <th className="py-2 pr-3" scope="col">
                        Operation
                      </th>
                      <th className="py-2" scope="col">
                        Path
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {workflow.underlyingEndpoints.map((endpoint) => (
                      <tr className="border-t border-slate-100" key={endpoint.operationId}>
                        <td className="py-2 pr-3 font-mono text-xs">
                          {endpoint.method}
                        </td>
                        <td className="py-2 pr-3 font-mono text-xs">
                          {endpoint.operationId}
                        </td>
                        <td className="py-2 font-mono text-xs text-slate-600">
                          {endpoint.path}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <Button
                disabled={approveWorkflow.isPending}
                onClick={() => handleApprove(workflow)}
                size="sm"
              >
                <Check className="h-4 w-4" />
                Approve
              </Button>
              <Button
                onClick={() => setRejecting(workflow)}
                size="sm"
                variant="destructive"
              >
                <X className="h-4 w-4" />
                Reject
              </Button>
              <Button onClick={() => setEditing(workflow)} size="sm" variant="secondary">
                <Pencil className="h-4 w-4" />
                Edit
              </Button>
              <Button asChild size="sm" variant="ghost">
                <Link href="/graph" onClick={() => handleViewInGraph(workflow)}>
                  <GitBranch className="h-4 w-4" />
                  View in graph
                </Link>
              </Button>
            </div>
          </div>
        </Card>
      ))}

      <EditWorkflowDialog
        onOpenChange={(open) => {
          if (!open) setEditing(null);
        }}
        onSaved={(message) =>
          setFeedback({
            type: message.startsWith("Updated") ? "success" : "error",
            message,
          })
        }
        open={Boolean(editing)}
        workflow={editing}
      />

      <RejectWorkflowDialog
        onOpenChange={(open) => {
          if (!open) setRejecting(null);
        }}
        onRejected={(message, isError) =>
          setFeedback({ type: isError ? "error" : "success", message })
        }
        open={Boolean(rejecting)}
        workflow={rejecting}
      />
    </div>
  );
}
