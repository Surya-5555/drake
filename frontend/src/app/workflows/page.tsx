import { WorkflowReviewTable } from "@/components/workflows/workflow-review-table";

export default function WorkflowReviewPage() {
  return (
    <div className="space-y-5">
      <section>
        <h2 className="text-xl font-semibold text-slate-950">Workflow Review</h2>
        <p className="mt-1 text-sm text-slate-500">
          Approve, reject, or edit graph-discovered workflow clusters before FastMCP
          registration.
        </p>
      </section>
      <WorkflowReviewTable />
    </div>
  );
}

