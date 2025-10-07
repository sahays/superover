import { filesApi as filesApiClass } from './api/files';
import { FileFilters } from '@/types';

// Export scene analyzer API
export { sceneAnalyzerApi } from './api/scene-analyzer';
export type { SceneAnalysisJob, SignedUrlResponse, CreateJobRequest, CreateJobResponse } from './api/scene-analyzer';

// Export the files API
export const filesApi = {
  getFiles: (params?: {
    page?: number;
    limit?: number;
    filters?: FileFilters;
  }) => filesApiClass.getFiles(params),
  getFile: (id: string) => filesApiClass.getFile(id),
  getFileMetadata: (id: string) => filesApiClass.getFileMetadata(id),
  uploadFile: (file: File | Blob, onProgress?: (progress: number) => void) => filesApiClass.uploadFile(file, onProgress),
  deleteFile: (id: string) => filesApiClass.deleteFile(id),
};