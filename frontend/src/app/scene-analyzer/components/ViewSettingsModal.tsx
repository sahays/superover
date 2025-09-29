'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { X, Eye, Settings, Video, Clock } from 'lucide-react';
import { Portal } from '@/components/ui/portal';

interface Pipeline {
  id: string;
  name: string;
  createdAt: string;
  lastRun: string | null;
  status: 'completed' | 'running' | 'draft';
  settings: {
    compressionRate: '240p' | '360p' | '480p' | '720p' | '1080p' | 'none';
    chunkLength: number;
  };
}

interface ViewSettingsModalProps {
  open: boolean;
  onClose: () => void;
  pipeline: Pipeline;
}

export function ViewSettingsModal({ open, onClose, pipeline }: ViewSettingsModalProps) {
  if (!open) return null;

  return (
    <Portal>
      <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black bg-opacity-50">
      <Card className="w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Eye className="h-5 w-5 text-blue-600" />
            </div>
            <CardTitle>Pipeline Settings</CardTitle>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Pipeline Info */}
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-medium mb-3">Pipeline Information</h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">Name</span>
                  <span className="font-medium">{pipeline.name}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">Type</span>
                  <Badge variant="outline">Scene Analyzer</Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">Status</span>
                  <Badge variant="outline" className={
                    pipeline.status === 'completed' ? 'bg-green-100 text-green-800 border-green-200' :
                    pipeline.status === 'running' ? 'bg-blue-100 text-blue-800 border-blue-200' :
                    'bg-gray-100 text-gray-800 border-gray-200'
                  }>
                    {pipeline.status}
                  </Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">Created</span>
                  <span className="font-medium">{pipeline.createdAt}</span>
                </div>
                {pipeline.lastRun && (
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-muted-foreground">Last Run</span>
                    <span className="font-medium">{pipeline.lastRun}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Settings */}
            <div>
              <h3 className="text-lg font-medium mb-3 flex items-center gap-2">
                <Settings className="h-4 w-4" />
                Configuration
              </h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <Video className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">Compression Rate</span>
                  </div>
                  <Badge variant="outline">{pipeline.settings.compressionRate}</Badge>
                </div>
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">Chunk Length</span>
                  </div>
                  <span className="font-medium">{pipeline.settings.chunkLength} seconds</span>
                </div>
              </div>
            </div>

            {/* Note */}
            <div className="bg-blue-50 p-4 rounded-lg">
              <p className="text-sm text-blue-700">
                <strong>Note:</strong> Pipeline settings are immutable and cannot be changed after creation.
                To use different settings, create a new pipeline.
              </p>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <Button variant="outline" onClick={onClose} className="flex-1">
              Close
            </Button>
            <Button
              className="flex-1"
              disabled={pipeline.status === 'running'}
            >
              {pipeline.status === 'running' ? 'Running...' : 'Run Again'}
            </Button>
          </div>
        </CardContent>
      </Card>
      </div>
    </Portal>
  );
}