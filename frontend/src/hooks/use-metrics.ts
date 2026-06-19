import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/workflows";
import { queryKeys } from "@/lib/query-keys";

export function useMetrics() {
  return useQuery({ queryKey: queryKeys.metrics, queryFn: api.metrics });
}

