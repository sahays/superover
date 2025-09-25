import { create } from 'zustand';
import { FileUploadProgress } from '@/types';

interface FilesStore {
  selectedFiles: string[];
  uploadProgress: Record<string, FileUploadProgress>;

  // Actions
  setSelectedFiles: (files: string[]) => void;
  toggleFileSelection: (fileId: string) => void;
  clearSelection: () => void;
  updateUploadProgress: (progress: FileUploadProgress) => void;
  removeUploadProgress: (fileId: string) => void;
  clearUploadProgress: () => void;
}

export const useFilesStore = create<FilesStore>((set) => ({
  // Initial state
  selectedFiles: [],
  uploadProgress: {},

  // Actions
  setSelectedFiles: (files) =>
    set({ selectedFiles: files }),

  toggleFileSelection: (fileId) =>
    set((state) => ({
      selectedFiles: state.selectedFiles.includes(fileId)
        ? state.selectedFiles.filter((id) => id !== fileId)
        : [...state.selectedFiles, fileId],
    })),

  clearSelection: () =>
    set({ selectedFiles: [] }),

  updateUploadProgress: (progress) =>
    set((state) => ({
      uploadProgress: {
        ...state.uploadProgress,
        [progress.fileId]: progress,
      },
    })),

  removeUploadProgress: (fileId) =>
    set((state) => {
      const newProgress = { ...state.uploadProgress };
      delete newProgress[fileId];
      return { uploadProgress: newProgress };
    }),

  clearUploadProgress: () =>
    set({ uploadProgress: {} }),
}));