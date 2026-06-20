import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/workflows";
import { queryKeys } from "@/lib/query-keys";

export function useOverview() {
  return useQuery({
    queryKey: queryKeys.overview,
    queryFn: api.overview,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      const isRunning = [
        data.ingestionStatus,
        data.graphStatus,
        data.clusteringStatus,
        data.mcpRuntimeStatus,
      ].some((status) => status === "running");
      return isRunning ? 2000 : false;
    },
  });
}

