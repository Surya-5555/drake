import { create } from "zustand";

interface ReviewState {
  selectedWorkflowId: string | null;
  graphClusterFilter: string | null;
  setSelectedWorkflowId: (workflowId: string | null) => void;
  setGraphClusterFilter: (clusterId: string | null) => void;
}

export const useReviewStore = create<ReviewState>((set) => ({
  selectedWorkflowId: null,
  graphClusterFilter: null,
  setSelectedWorkflowId: (selectedWorkflowId) => set({ selectedWorkflowId }),
  setGraphClusterFilter: (graphClusterFilter) => set({ graphClusterFilter }),
}));

