import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/workflows";
import { queryKeys } from "@/lib/query-keys";

export function useGraph() {
  return useQuery({ queryKey: queryKeys.graph, queryFn: api.graph });
}

