import { apiClient } from './client';
import { Pipeline, ApiResponse } from '@/types';

export class WorkflowsApi {
  // Get available pipelines
  async getPipelines(): Promise<ApiResponse<Pipeline[]>> {
    return apiClient.get<ApiResponse<Pipeline[]>>('/workflows/pipelines');
  }

  // Get single pipeline by ID
  async getPipeline(id: string): Promise<ApiResponse<Pipeline>> {
    return apiClient.get<ApiResponse<Pipeline>>(`/workflows/pipelines/${id}`);
  }

  // Create new workflow (not implemented in MVP)
  async createWorkflow(workflow: {
    name: string;
    description: string;
    steps: unknown[];
  }): Promise<ApiResponse<Pipeline>> {
    return apiClient.post<ApiResponse<Pipeline>>('/workflows', workflow);
  }

  // Update workflow (not implemented in MVP)
  async updateWorkflow(id: string, updates: Partial<Pipeline>): Promise<ApiResponse<Pipeline>> {
    return apiClient.put<ApiResponse<Pipeline>>(`/workflows/${id}`, updates);
  }

  // Delete workflow (not implemented in MVP)
  async deleteWorkflow(id: string): Promise<ApiResponse<void>> {
    return apiClient.delete<ApiResponse<void>>(`/workflows/${id}`);
  }
}

export const workflowsApi = new WorkflowsApi();