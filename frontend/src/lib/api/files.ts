import { apiClient } from './client';
import { FileItem, ApiResponse, PaginatedResponse, FileFilters, FileMetadata } from '@/types';

export class FilesApi {
  // Get paginated list of files
  async getFiles(params?: {
    page?: number;
    limit?: number;
    filters?: FileFilters;
  }): Promise<PaginatedResponse<FileItem>> {
    const searchParams = new URLSearchParams();

    if (params?.page) searchParams.set('page', params.page.toString());
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.filters?.search) searchParams.set('search', params.filters.search);
    if (params?.filters?.type?.length) {
      params.filters.type.forEach(type => searchParams.append('type', type));
    }
    if (params?.filters?.status?.length) {
      params.filters.status.forEach(status => searchParams.append('status', status));
    }

    return apiClient.get<PaginatedResponse<FileItem>>(`/files?${searchParams.toString()}`);
  }

  // Get single file by ID
  async getFile(id: string): Promise<ApiResponse<FileItem>> {
    return apiClient.get<ApiResponse<FileItem>>(`/files/${id}`);
  }

  // Upload file
  async uploadFile(
    file: File | Blob,
    onProgress?: (progress: number) => void
  ): Promise<ApiResponse<FileItem>> {
    const formData = new FormData();
    formData.append('file', file);

    return apiClient.uploadFile<ApiResponse<FileItem>>(
      '/files/upload',
      formData,
      (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded / progressEvent.total) * 100);
          onProgress(progress);
        }
      }
    );
  }

  // Delete file
  async deleteFile(id: string): Promise<ApiResponse<void>> {
    return apiClient.delete<ApiResponse<void>>(`/files/${id}`);
  }

  // Get file metadata
  async getFileMetadata(id: string): Promise<ApiResponse<FileMetadata>> {
    return apiClient.get<ApiResponse<FileMetadata>>(`/files/${id}/metadata`);
  }

  // Download file
  async downloadFile(id: string, filename?: string): Promise<void> {
    return apiClient.downloadFile(`/files/${id}/download`, filename);
  }
}

export const filesApi = new FilesApi();