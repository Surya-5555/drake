import { AuditTrail } from "@/components/audit/audit-trail";

export default function AuditPage() {
  return (
    <div className="space-y-5">
      <section>
        <h2 className="text-xl font-semibold text-slate-950">Audit Trail</h2>
        <p className="mt-1 text-sm text-slate-500">
          Track workflow lifecycle events from generation through controlled FastMCP
          registration.
        </p>
      </section>
      <AuditTrail />
    </div>
  );
}

