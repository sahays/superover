import { apiClient } from './client';
import { OutputFile, AnalysisResult, ApiResponse, PaginatedResponse } from '@/types';

export class OutputsApi {
  // Get paginated list of output files
  async getOutputs(params?: {
    page?: number;
    limit?: number;
    executionId?: string;
    fileType?: string;
  }): Promise<PaginatedResponse<OutputFile>> {
    const searchParams = new URLSearchParams();

    if (params?.page) searchParams.set('page', params.page.toString());
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.executionId) searchParams.set('executionId', params.executionId);
    if (params?.fileType) searchParams.set('fileType', params.fileType);

    return apiClient.get<PaginatedResponse<OutputFile>>(`/outputs?${searchParams.toString()}`);
  }

  // Get single output file by ID
  async getOutput(id: string): Promise<ApiResponse<OutputFile>> {
    return apiClient.get<ApiResponse<OutputFile>>(`/outputs/${id}`);
  }

  // Get download URL for output file
  async getDownloadUrl(id: string): Promise<ApiResponse<{ downloadUrl: string; expiresAt: string }>> {
    return apiClient.get<ApiResponse<{ downloadUrl: string; expiresAt: string }>>(`/outputs/${id}/download`);
  }

  // Download output file
  async downloadOutput(id: string, filename?: string): Promise<void> {
    return apiClient.downloadFile(`/outputs/${id}/download`, filename);
  }

  // Delete output file
  async deleteOutput(id: string): Promise<ApiResponse<void>> {
    return apiClient.delete<ApiResponse<void>>(`/outputs/${id}`);
  }

  // Get analysis results for an execution
  async getAnalysisResults(executionId: string): Promise<ApiResponse<AnalysisResult>> {
    return apiClient.get<ApiResponse<AnalysisResult>>(`/outputs/${executionId}/analysis`);
  }
}

export const outputsApi = new OutputsApi();