'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { X, Upload, Eye } from 'lucide-react';
import { Portal } from '@/components/ui/portal';

interface CreateSceneAnalyzerModalProps {
  open: boolean;
  onClose: () => void;
}

export function CreateSceneAnalyzerModal({ open, onClose }: CreateSceneAnalyzerModalProps) {
  const [pipelineName, setPipelineName] = useState('');
  const [compressionRate, setCompressionRate] = useState<string>('720p');
  const [chunkLength, setChunkLength] = useState<number>(30);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleSubmit = async () => {
    if (!pipelineName.trim() || !selectedFile) return;

    setIsSubmitting(true);
    try {
      // TODO: Replace with actual API call
      console.log('Creating Scene Analyzer pipeline:', {
        name: pipelineName,
        file: selectedFile,
        settings: {
          compressionRate,
          chunkLength,
        },
      });

      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));

      alert('Scene Analyzer pipeline created successfully!');
      onClose();
      // Reset form
      setPipelineName('');
      setSelectedFile(null);
      setCompressionRate('720p');
      setChunkLength(30);
    } catch (error) {
      console.error('Failed to create pipeline:', error);
      alert('Failed to create pipeline. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const canSubmit = pipelineName.trim() && selectedFile && !isSubmitting;

  if (!open) return null;

  return (
    <Portal>
      <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black bg-opacity-50" onClick={onClose}>
        <Card className="w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Eye className="h-5 w-5 text-blue-600" />
            </div>
            <CardTitle>Create Scene Analyzer</CardTitle>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Pipeline Name */}
          <div className="space-y-2">
            <Label htmlFor="name">Pipeline Name</Label>
            <Input
              id="name"
              placeholder="e.g., Movie Trailer Analysis"
              value={pipelineName}
              onChange={(e) => setPipelineName(e.target.value)}
            />
          </div>

          {/* File Upload */}
          <div className="space-y-2">
            <Label htmlFor="file">Video File</Label>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-gray-400 transition-colors relative">
              <Upload className="mx-auto h-8 w-8 text-gray-400 mb-2" />
              <div className="space-y-1">
                <p className="text-sm font-medium">Click to upload video file</p>
                <p className="text-xs text-muted-foreground">MP4, MOV, AVI up to 500MB</p>
              </div>
              <input
                type="file"
                accept="video/*"
                onChange={handleFileSelect}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
            </div>
            {selectedFile && (
              <div className="text-sm text-green-600">
                Selected: {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(1)} MB)
              </div>
            )}
          </div>

          {/* Settings */}
          <div className="space-y-4">
            <h3 className="text-lg font-medium">Settings</h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="compression">Compression Rate</Label>
                <Select value={compressionRate} onValueChange={setCompressionRate}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="240p">240p</SelectItem>
                    <SelectItem value="360p">360p</SelectItem>
                    <SelectItem value="480p">480p</SelectItem>
                    <SelectItem value="720p">720p</SelectItem>
                    <SelectItem value="1080p">1080p</SelectItem>
                    <SelectItem value="none">None</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="chunk">Chunk Length (seconds)</Label>
                <Input
                  id="chunk"
                  type="number"
                  min="1"
                  max="60"
                  value={chunkLength}
                  onChange={(e) => setChunkLength(parseInt(e.target.value) || 30)}
                />
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <Button variant="outline" onClick={onClose} className="flex-1">
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="flex-1"
            >
              {isSubmitting ? 'Creating...' : 'Create Pipeline'}
            </Button>
          </div>
        </CardContent>
        </Card>
      </div>
    </Portal>
  );
}