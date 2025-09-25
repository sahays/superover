'use client';

import React, { useState } from 'react';
import Image from 'next/image';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useFiles, useFileDelete } from '@/hooks/useFiles';
import { useFilesStore } from '@/stores/files';
import { FileUploader } from '@/features/files/components/FileUploader';
import {
  Upload,
  Search,
  Download,
  Trash2,
  Play,
  FileText,
  Music,
  Video,
  Image as ImageIcon,
  File
} from 'lucide-react';
import {
  formatFileSize,
  formatRelativeTime,
  getFileTypeCategory,
  truncateText
} from '@/lib/utils';
import { FileStatus } from '@/types';

const getFileIcon = (mimeType: string) => {
  const category = getFileTypeCategory(mimeType);
  switch (category) {
    case 'video': return Video;
    case 'audio': return Music;
    case 'image': return ImageIcon;
    case 'document': return FileText;
    default: return File;
  }
};

const getStatusColor = (status: FileStatus) => {
  switch (status) {
    case 'uploaded': return 'bg-green-100 text-green-800 border-green-200';
    case 'uploading': return 'bg-blue-100 text-blue-800 border-blue-200';
    case 'processing': return 'bg-purple-100 text-purple-800 border-purple-200';
    case 'failed': return 'bg-red-100 text-red-800 border-red-200';
    default: return 'bg-gray-100 text-gray-800 border-gray-200';
  }
};

export default function FilesPage() {
  const [search, setSearch] = useState('');
  const [selectedStatus, setSelectedStatus] = useState<FileStatus | 'all'>('all');
  const [showUploader, setShowUploader] = useState(false);

  // Get files data
  const { data: filesData, isLoading } = useFiles({
    filters: {
      search: search || undefined,
      status: selectedStatus === 'all' ? undefined : [selectedStatus],
    }
  });

  const deleteFile = useFileDelete();
  const { selectedFiles, toggleFileSelection, clearSelection } = useFilesStore();

  const files = filesData?.data || [];
  const pagination = filesData?.pagination;

  const handleDeleteFile = (fileId: string) => {
    deleteFile.mutate(fileId);
  };

  const handleSelectAll = () => {
    if (selectedFiles.length === files.length) {
      clearSelection();
    } else {
      // Select all current files
      files.forEach(file => {
        if (!selectedFiles.includes(file.id)) {
          toggleFileSelection(file.id);
        }
      });
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Files</h1>
          <p className="text-gray-600">
            Manage your uploaded media files and their processing status
          </p>
        </div>
        <Button onClick={() => setShowUploader(true)}>
          <Upload className="mr-2 h-4 w-4" />
          Upload Files
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <Input
                placeholder="Search files..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="flex items-center gap-2">
              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value as FileStatus | 'all')}
                className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              >
                <option value="all">All Status</option>
                <option value="uploaded">Uploaded</option>
                <option value="uploading">Uploading</option>
                <option value="processing">Processing</option>
                <option value="failed">Failed</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Files List */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>
              Files ({pagination?.total || 0})
            </CardTitle>
            {selectedFiles.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-600">
                  {selectedFiles.length} selected
                </span>
                <Button variant="outline" size="sm" onClick={clearSelection}>
                  Clear
                </Button>
                <Button variant="destructive" size="sm">
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete Selected
                </Button>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
                <p className="mt-2 text-sm text-gray-600">Loading files...</p>
              </div>
            </div>
          ) : files.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">No files found</h3>
              <p className="mt-1 text-sm text-gray-500">
                {search || selectedStatus !== 'all'
                  ? 'Try adjusting your search or filters.'
                  : 'Get started by uploading your first file.'
                }
              </p>
              {!search && selectedStatus === 'all' && (
                <div className="mt-6">
                  <Button onClick={() => setShowUploader(true)}>
                    <Upload className="mr-2 h-4 w-4" />
                    Upload Files
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {/* Select all header */}
              <div className="flex items-center gap-3 pb-2 border-b">
                <input
                  type="checkbox"
                  checked={selectedFiles.length === files.length}
                  onChange={handleSelectAll}
                  className="rounded border-gray-300 text-primary focus:ring-primary"
                />
                <span className="text-sm font-medium text-gray-700">
                  Select All
                </span>
              </div>

              {/* Files grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {files.map((file) => {
                  const FileIcon = getFileIcon(file.type);
                  const isSelected = selectedFiles.includes(file.id);

                  return (
                    <div
                      key={file.id}
                      className={`relative group rounded-lg border p-4 transition-all ${
                        isSelected
                          ? 'border-primary bg-primary/5'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      {/* Selection checkbox */}
                      <div className="absolute top-2 left-2">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleFileSelection(file.id)}
                          className="rounded border-gray-300 text-primary focus:ring-primary"
                        />
                      </div>

                      {/* File preview/icon */}
                      <div className="flex items-center justify-center h-20 mb-4 mt-6">
                        {file.thumbnailUrl ? (
                          <Image
                            src={file.thumbnailUrl}
                            alt={file.name}
                            width={80}
                            height={80}
                            className="max-h-20 max-w-full object-contain rounded"
                          />
                        ) : (
                          <div className="p-4 rounded-lg bg-gray-100">
                            <FileIcon className="h-8 w-8 text-gray-600" />
                          </div>
                        )}
                      </div>

                      {/* File info */}
                      <div className="space-y-2">
                        <h4 className="font-medium text-sm text-gray-900 truncate" title={file.name}>
                          {truncateText(file.name, 30)}
                        </h4>
                        <div className="flex items-center justify-between text-xs text-gray-500">
                          <span>{formatFileSize(file.size)}</span>
                          <span>{formatRelativeTime(file.uploadedAt)}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <Badge className={getStatusColor(file.status)}>
                            {file.status}
                          </Badge>
                          {file.metadata?.duration && (
                            <span className="text-xs text-gray-500">
                              {Math.round(file.metadata.duration)}s
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <div className="flex items-center gap-1">
                          {file.status === 'uploaded' && (
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                              <Play className="h-4 w-4" />
                            </Button>
                          )}
                          <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                            <Download className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                            onClick={() => handleDeleteFile(file.id)}
                            disabled={deleteFile.isPending}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* File Uploader Modal */}
      {showUploader && (
        <FileUploader onClose={() => setShowUploader(false)} />
      )}
    </div>
  );
}