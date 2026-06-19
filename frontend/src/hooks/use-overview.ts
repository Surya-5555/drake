import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/workflows";
import { queryKeys } from "@/lib/query-keys";

export function useOverview() {
  return useQuery({ queryKey: queryKeys.overview, queryFn: api.overview });
}

