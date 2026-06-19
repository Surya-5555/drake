import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/workflows";
import { queryKeys } from "@/lib/query-keys";

export function useAuditEvents() {
  return useQuery({ queryKey: queryKeys.audit, queryFn: api.auditEvents });
}

