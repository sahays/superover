import { apiClient } from './client';
import { ApiResponse } from '@/types';

interface Workflow {
  id: string;
  name: string;
  description: string;
  type: string;
  status: 'active' | 'draft' | 'inactive';
  createdAt: string;
  updatedAt: string;
}

export class WorkflowsApi {
  // Get available workflows
  async getWorkflows(): Promise<ApiResponse<Workflow[]>> {
    return apiClient.get<ApiResponse<Workflow[]>>('/workflows');
  }

  // Get single workflow by ID
  async getWorkflow(id: string): Promise<ApiResponse<Workflow>> {
    return apiClient.get<ApiResponse<Workflow>>(`/workflows/${id}`);
  }

  // Create new workflow
  async createWorkflow(workflow: {
    name: string;
    description: string;
    type: string;
  }): Promise<ApiResponse<Workflow>> {
    return apiClient.post<ApiResponse<Workflow>>('/workflows', workflow);
  }

  // Update workflow
  async updateWorkflow(id: string, updates: Partial<Workflow>): Promise<ApiResponse<Workflow>> {
    return apiClient.put<ApiResponse<Workflow>>(`/workflows/${id}`, updates);
  }

  // Delete workflow
  async deleteWorkflow(id: string): Promise<ApiResponse<void>> {
    return apiClient.delete<ApiResponse<void>>(`/workflows/${id}`);
  }
}

export const workflowsApi = new WorkflowsApi();