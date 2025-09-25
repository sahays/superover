'use client';

import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { useFileUpload } from '@/hooks/useFiles';
import { useFilesStore } from '@/stores/files';
import {
  Upload,
  X,
  File,
  CheckCircle2,
  AlertCircle,
  Video,
  Music,
  Image as ImageIcon,
  FileText
} from 'lucide-react';
import { formatFileSize, getFileTypeCategory, generateId } from '@/lib/utils';

interface FileUploaderProps {
  onClose: () => void;
}

interface FileItem {
  id: string;
  file: File;
  status: 'pending' | 'uploading' | 'completed' | 'failed';
  progress: number;
  error?: string;
}

const getFileIcon = (type: string) => {
  const category = getFileTypeCategory(type);
  switch (category) {
    case 'video': return Video;
    case 'audio': return Music;
    case 'image': return ImageIcon;
    case 'document': return FileText;
    default: return File;
  }
};

const ACCEPTED_TYPES = {
  'video/*': ['.mp4', '.mov', '.avi', '.mkv', '.webm'],
  'audio/*': ['.mp3', '.wav', '.flac', '.aac', '.ogg'],
  'image/*': ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
  'application/json': ['.json'],
  'text/*': ['.txt', '.srt', '.vtt']
};

export function FileUploader({ onClose }: FileUploaderProps) {
  const [fileItems, setFileItems] = useState<FileItem[]>([]);
  const uploadFile = useFileUpload();
  const { uploadProgress } = useFilesStore();

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFileItems: FileItem[] = acceptedFiles.map(file => ({
      id: generateId('file'),
      file,
      status: 'pending',
      progress: 0,
    }));

    setFileItems(prev => [...prev, ...newFileItems]);
  }, []);

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: 2 * 1024 * 1024 * 1024, // 2GB
    multiple: true,
  });

  const removeFile = (fileId: string) => {
    setFileItems(prev => prev.filter(item => item.id !== fileId));
  };

  const uploadFiles = async () => {
    const pendingFiles = fileItems.filter(item => item.status === 'pending');

    // Upload files sequentially to avoid overwhelming the server
    for (const fileItem of pendingFiles) {
      setFileItems(prev => prev.map(item =>
        item.id === fileItem.id
          ? { ...item, status: 'uploading' }
          : item
      ));

      try {
        await uploadFile.mutateAsync({
          file: fileItem.file,
          fileId: fileItem.id
        });

        setFileItems(prev => prev.map(item =>
          item.id === fileItem.id
            ? { ...item, status: 'completed', progress: 100 }
            : item
        ));
      } catch (error) {
        setFileItems(prev => prev.map(item =>
          item.id === fileItem.id
            ? {
                ...item,
                status: 'failed',
                progress: 0,
                error: error instanceof Error ? error.message : 'Upload failed'
              }
            : item
        ));
      }
    }
  };

  const retryFile = async (fileItem: FileItem) => {
    setFileItems(prev => prev.map(item =>
      item.id === fileItem.id
        ? { ...item, status: 'uploading', progress: 0, error: undefined }
        : item
    ));

    try {
      await uploadFile.mutateAsync({
        file: fileItem.file,
        fileId: fileItem.id
      });

      setFileItems(prev => prev.map(item =>
        item.id === fileItem.id
          ? { ...item, status: 'completed', progress: 100 }
          : item
      ));
    } catch (error) {
      setFileItems(prev => prev.map(item =>
        item.id === fileItem.id
          ? {
              ...item,
              status: 'failed',
              progress: 0,
              error: error instanceof Error ? error.message : 'Upload failed'
            }
          : item
      ));
    }
  };

  // Update progress from store
  React.useEffect(() => {
    setFileItems(prev => prev.map(item => {
      const progress = uploadProgress[item.id];
      if (progress && item.status === 'uploading') {
        return {
          ...item,
          progress: progress.progress,
          status: progress.status === 'completed' ? 'completed' :
                  progress.status === 'failed' ? 'failed' : item.status,
          error: progress.error,
        };
      }
      return item;
    }));
  }, [uploadProgress]);

  const pendingFiles = fileItems.filter(item => item.status === 'pending');
  const uploadingFiles = fileItems.filter(item => item.status === 'uploading');
  const completedFiles = fileItems.filter(item => item.status === 'completed');
  const failedFiles = fileItems.filter(item => item.status === 'failed');

  const canUpload = pendingFiles.length > 0;
  const isUploading = uploadingFiles.length > 0;
  const allCompleted = fileItems.length > 0 && completedFiles.length === fileItems.length;

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
      <Card className="w-full max-w-2xl max-h-[80vh] overflow-hidden">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
          <CardTitle>Upload Files</CardTitle>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>

        <CardContent className="space-y-4 max-h-[60vh] overflow-y-auto">
          {/* Drop Zone */}
          <div
            {...getRootProps()}
            className={`
              relative border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer
              ${isDragActive
                ? 'border-primary bg-primary/5'
                : 'border-gray-300 hover:border-gray-400'
              }
            `}
          >
            <input {...getInputProps()} />
            <Upload className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-2 text-sm text-gray-600">
              {isDragActive
                ? 'Drop the files here...'
                : 'Drag & drop files here, or click to select files'
              }
            </p>
            <p className="text-xs text-gray-500 mt-1">
              Supports video, audio, image, and text files up to 2GB
            </p>
          </div>

          {/* File Rejections */}
          {fileRejections.length > 0 && (
            <div className="space-y-2">
              {fileRejections.map(({ file, errors }) => (
                <div key={file.name} className="flex items-center gap-2 p-2 bg-red-50 border border-red-200 rounded">
                  <AlertCircle className="h-4 w-4 text-red-600" />
                  <span className="text-sm text-red-800">
                    {file.name}: {errors[0]?.message}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* File List */}
          {fileItems.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="font-medium">Files ({fileItems.length})</h4>
                <div className="text-xs text-gray-500">
                  {completedFiles.length > 0 && (
                    <span className="text-green-600">{completedFiles.length} completed</span>
                  )}
                  {failedFiles.length > 0 && (
                    <span className="text-red-600 ml-2">{failedFiles.length} failed</span>
                  )}
                </div>
              </div>

              <div className="space-y-2 max-h-60 overflow-y-auto">
                {fileItems.map((item) => {
                  const FileIcon = getFileIcon(item.file.type);

                  return (
                    <div
                      key={item.id}
                      className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg"
                    >
                      <div className="p-2 bg-white rounded">
                        <FileIcon className="h-4 w-4 text-gray-600" />
                      </div>

                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {item.file.name}
                        </p>
                        <p className="text-xs text-gray-500">
                          {formatFileSize(item.file.size)}
                        </p>

                        {item.status === 'uploading' && (
                          <div className="mt-1">
                            <Progress value={item.progress} className="h-1" />
                          </div>
                        )}

                        {item.error && (
                          <p className="text-xs text-red-600 mt-1">{item.error}</p>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        {item.status === 'pending' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => removeFile(item.id)}
                            className="h-8 w-8 p-0"
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        )}

                        {item.status === 'uploading' && (
                          <div className="text-xs text-blue-600">
                            {item.progress}%
                          </div>
                        )}

                        {item.status === 'completed' && (
                          <CheckCircle2 className="h-4 w-4 text-green-600" />
                        )}

                        {item.status === 'failed' && (
                          <div className="flex items-center gap-1">
                            <AlertCircle className="h-4 w-4 text-red-600" />
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => retryFile(item)}
                              className="text-xs h-6 px-2"
                            >
                              Retry
                            </Button>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </CardContent>

        {/* Footer Actions */}
        <div className="p-6 pt-0 flex items-center justify-between">
          <div className="text-sm text-gray-600">
            {fileItems.length > 0 && (
              <>
                {completedFiles.length}/{fileItems.length} uploaded
                {isUploading && ' (uploading...)'}
              </>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={onClose}>
              {allCompleted ? 'Close' : 'Cancel'}
            </Button>

            {!allCompleted && (
              <Button
                onClick={uploadFiles}
                disabled={!canUpload || isUploading}
                loading={isUploading}
              >
                Upload {pendingFiles.length > 0 ? `${pendingFiles.length} ` : ''}Files
              </Button>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}