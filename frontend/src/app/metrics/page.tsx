import { MetricsDashboard } from "@/components/metrics/metrics-dashboard";

export default function MetricsPage() {
  return (
    <div className="space-y-5">
      <section>
        <h2 className="text-xl font-semibold text-slate-950">Metrics</h2>
        <p className="mt-1 text-sm text-slate-500">
          Quantify endpoint reduction, token savings, workflow coverage, and approval
          posture.
        </p>
      </section>
      <MetricsDashboard />
    </div>
  );
}

