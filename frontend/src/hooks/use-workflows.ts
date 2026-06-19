import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/workflows";
import { queryKeys } from "@/lib/query-keys";

function invalidateGovernanceQueries(queryClient: ReturnType<typeof useQueryClient>) {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: queryKeys.workflows }),
    queryClient.invalidateQueries({ queryKey: queryKeys.overview }),
    queryClient.invalidateQueries({ queryKey: queryKeys.audit }),
    queryClient.invalidateQueries({ queryKey: queryKeys.metrics }),
    queryClient.invalidateQueries({ queryKey: queryKeys.graph }),
  ]);
}

export function usePendingWorkflows() {
  return useQuery({
    queryKey: queryKeys.workflows,
    queryFn: api.pendingWorkflows,
  });
}

export function useApproveWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.approveWorkflow,
    onSuccess: async () => {
      await api.reloadMcp();
      await invalidateGovernanceQueries(queryClient);
    },
  });
}

export function useRejectWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ workflowId, reason }: { workflowId: string; reason: string }) =>
      api.rejectWorkflow(workflowId, reason),
    onSuccess: () => invalidateGovernanceQueries(queryClient),
  });
}

export function useUpdateWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.updateWorkflow,
    onSuccess: () => invalidateGovernanceQueries(queryClient),
  });
}
