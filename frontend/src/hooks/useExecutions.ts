import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { executionsApi } from '@/lib/api/executions';
import { ExecutionFilters, WorkflowParameters } from '@/types';
import { useAppStore } from '@/stores/app';

// Query keys
export const executionKeys = {
  all: ['executions'] as const,
  lists: () => [...executionKeys.all, 'list'] as const,
  list: (filters: ExecutionFilters & { page?: number; limit?: number }) => [...executionKeys.lists(), filters] as const,
  details: () => [...executionKeys.all, 'detail'] as const,
  detail: (id: string) => [...executionKeys.details(), id] as const,
  status: (id: string) => [...executionKeys.all, 'status', id] as const,
};

// Custom hooks
export function useExecutions(params?: {
  page?: number;
  limit?: number;
  filters?: ExecutionFilters;
}) {
  return useQuery({
    queryKey: executionKeys.list(params || {}),
    queryFn: () => executionsApi.getExecutions(params),
  });
}

export function useExecution(id: string) {
  return useQuery({
    queryKey: executionKeys.detail(id),
    queryFn: () => executionsApi.getExecution(id),
    enabled: !!id,
  });
}

export function useExecutionStatus(id: string, enabled: boolean = true) {
  return useQuery({
    queryKey: executionKeys.status(id),
    queryFn: () => executionsApi.getExecutionStatus(id),
    enabled: enabled && !!id,
    refetchInterval: (query) => {
      // Refetch every 3 seconds if execution is running
      const execution = query.state.data?.data;
      if (execution?.status === 'running' || execution?.status === 'pending') {
        return 3000;
      }
      return false;
    },
  });
}

export function useCreateExecution() {
  const queryClient = useQueryClient();
  const addNotification = useAppStore((state) => state.addNotification);

  return useMutation({
    mutationFn: (execution: {
      sourceFileId: string;
      workflowType: string;
      parameters?: WorkflowParameters;
    }) => executionsApi.createExecution(execution),
    onSuccess: (data) => {
      // Invalidate executions queries
      queryClient.invalidateQueries({ queryKey: executionKeys.lists() });

      addNotification({
        type: 'success',
        title: 'Execution Started',
        message: 'Workflow execution has been started successfully.',
        actionUrl: `/executions/${data.data?.id}`,
      });
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Execution Failed',
        message: error instanceof Error ? error.message : 'Failed to start execution.',
      });
    },
  });
}

export function useRetryExecution() {
  const queryClient = useQueryClient();
  const addNotification = useAppStore((state) => state.addNotification);

  return useMutation({
    mutationFn: executionsApi.retryExecution,
    onSuccess: (data, executionId) => {
      // Invalidate specific execution and list queries
      queryClient.invalidateQueries({ queryKey: executionKeys.detail(executionId) });
      queryClient.invalidateQueries({ queryKey: executionKeys.lists() });

      addNotification({
        type: 'success',
        title: 'Execution Retried',
        message: 'Workflow execution has been retried successfully.',
        actionUrl: `/executions/${data.data?.id}`,
      });
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Retry Failed',
        message: error instanceof Error ? error.message : 'Failed to retry execution.',
      });
    },
  });
}

export function useCancelExecution() {
  const queryClient = useQueryClient();
  const addNotification = useAppStore((state) => state.addNotification);

  return useMutation({
    mutationFn: executionsApi.cancelExecution,
    onSuccess: (data, executionId) => {
      // Invalidate specific execution and list queries
      queryClient.invalidateQueries({ queryKey: executionKeys.detail(executionId) });
      queryClient.invalidateQueries({ queryKey: executionKeys.lists() });

      addNotification({
        type: 'success',
        title: 'Execution Cancelled',
        message: 'Workflow execution has been cancelled successfully.',
      });
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Cancel Failed',
        message: error instanceof Error ? error.message : 'Failed to cancel execution.',
      });
    },
  });
}