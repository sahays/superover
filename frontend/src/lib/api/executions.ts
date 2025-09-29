import { apiClient } from './client';
import { WorkflowExecution, ApiResponse, PaginatedResponse, ExecutionFilters, WorkflowParameters } from '@/types';

export class ExecutionsApi {
  // Get paginated list of executions
  async getExecutions(params?: {
    page?: number;
    limit?: number;
    filters?: ExecutionFilters;
  }): Promise<PaginatedResponse<WorkflowExecution>> {
    const searchParams = new URLSearchParams();

    if (params?.page) searchParams.set('page', params.page.toString());
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.filters?.search) searchParams.set('search', params.filters.search);
    if (params?.filters?.status?.length) {
      params.filters.status.forEach(status => searchParams.append('status', status));
    }
    if (params?.filters?.pipelineId?.length) {
      params.filters.pipelineId.forEach(id => searchParams.append('pipelineId', id));
    }

    return apiClient.get<PaginatedResponse<WorkflowExecution>>(`/workflows/executions?${searchParams.toString()}`);
  }

  // Get single execution by ID
  async getExecution(id: string): Promise<ApiResponse<WorkflowExecution>> {
    return apiClient.get<ApiResponse<WorkflowExecution>>(`/workflows/executions/${id}`);
  }

  // Create new execution
  async createExecution(execution: {
    sourceFileId: string;
    pipelineId: string;
    parameters?: WorkflowParameters;
  }): Promise<ApiResponse<WorkflowExecution>> {
    return apiClient.post<ApiResponse<WorkflowExecution>>('/workflows/executions', execution);
  }

  // Retry failed execution
  async retryExecution(id: string): Promise<ApiResponse<WorkflowExecution>> {
    return apiClient.post<ApiResponse<WorkflowExecution>>(`/workflows/executions/${id}/retry`);
  }

  // Cancel running execution
  async cancelExecution(id: string): Promise<ApiResponse<void>> {
    return apiClient.post<ApiResponse<void>>(`/workflows/executions/${id}/cancel`);
  }

  // Get real-time execution status (for SSE or polling)
  async getExecutionStatus(id: string): Promise<ApiResponse<WorkflowExecution>> {
    return apiClient.get<ApiResponse<WorkflowExecution>>(`/workflows/executions/${id}/stream`);
  }
}

export const executionsApi = new ExecutionsApi();