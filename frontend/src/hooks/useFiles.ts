import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { filesApi } from '@/lib/api/files';
import { FileFilters } from '@/types';
import { useAppStore } from '@/stores/app';
import { useFilesStore } from '@/stores/files';

// Query keys
export const fileKeys = {
  all: ['files'] as const,
  lists: () => [...fileKeys.all, 'list'] as const,
  list: (filters: FileFilters & { page?: number; limit?: number }) => [...fileKeys.lists(), filters] as const,
  details: () => [...fileKeys.all, 'detail'] as const,
  detail: (id: string) => [...fileKeys.details(), id] as const,
  metadata: (id: string) => [...fileKeys.all, 'metadata', id] as const,
};

// Custom hooks
export function useFiles(params?: {
  page?: number;
  limit?: number;
  filters?: FileFilters;
}) {
  return useQuery({
    queryKey: fileKeys.list(params || {}),
    queryFn: () => filesApi.getFiles(params),
  });
}

export function useFile(id: string) {
  return useQuery({
    queryKey: fileKeys.detail(id),
    queryFn: () => filesApi.getFile(id),
    enabled: !!id,
  });
}

export function useFileMetadata(id: string) {
  return useQuery({
    queryKey: fileKeys.metadata(id),
    queryFn: () => filesApi.getFileMetadata(id),
    enabled: !!id,
  });
}

export function useFileUpload() {
  const queryClient = useQueryClient();
  const addNotification = useAppStore((state) => state.addNotification);
  const updateUploadProgress = useFilesStore((state) => state.updateUploadProgress);
  const removeUploadProgress = useFilesStore((state) => state.removeUploadProgress);

  return useMutation({
    mutationFn: async ({ file, fileId }: { file: File | Blob; fileId: string }) => {
      updateUploadProgress({
        fileId,
        fileName: file instanceof File ? file.name : 'unknown',
        progress: 0,
        status: 'uploading',
      });

      return filesApi.uploadFile(file, (progress) => {
        updateUploadProgress({
          fileId,
          fileName: file instanceof File ? file.name : 'unknown',
          progress,
          status: 'uploading',
        });
      });
    },
    onSuccess: (data, { fileId, file }) => {
      // Update upload progress to completed
      updateUploadProgress({
        fileId,
        fileName: file instanceof File ? file.name : 'unknown',
        progress: 100,
        status: 'completed',
      });

      // Remove progress after delay
      setTimeout(() => {
        removeUploadProgress(fileId);
      }, 2000);

      // Invalidate files query to refetch
      queryClient.invalidateQueries({ queryKey: fileKeys.lists() });

      // Show success notification
      addNotification({
        type: 'success',
        title: 'Upload Successful',
        message: `${file instanceof File ? file.name : 'File'} has been uploaded successfully.`,
      });
    },
    onError: (error, { fileId, file }) => {
      // Update upload progress to failed
      updateUploadProgress({
        fileId,
        fileName: file instanceof File ? file.name : 'unknown',
        progress: 0,
        status: 'failed',
        error: error instanceof Error ? error.message : 'Upload failed',
      });

      // Show error notification
      addNotification({
        type: 'error',
        title: 'Upload Failed',
        message: `Failed to upload ${file instanceof File ? file.name : 'file'}.`,
      });
    },
  });
}

export function useFileDelete() {
  const queryClient = useQueryClient();
  const addNotification = useAppStore((state) => state.addNotification);

  return useMutation({
    mutationFn: filesApi.deleteFile,
    onSuccess: () => {
      // Invalidate files queries
      queryClient.invalidateQueries({ queryKey: fileKeys.lists() });

      addNotification({
        type: 'success',
        title: 'File Deleted',
        message: 'File has been deleted successfully.',
      });
    },
    onError: (error) => {
      addNotification({
        type: 'error',
        title: 'Delete Failed',
        message: error instanceof Error ? error.message : 'Failed to delete file.',
      });
    },
  });
}