import { OpenApiGraph } from "@/components/graph/openapi-graph";

export default function GraphPage() {
  return (
    <div className="space-y-5">
      <section>
        <h2 className="text-xl font-semibold text-slate-950">
          Graph Visualization
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Inspect endpoint graph topology, Leiden communities, and workflow cluster
          boundaries.
        </p>
      </section>
      <OpenApiGraph />
    </div>
  );
}

