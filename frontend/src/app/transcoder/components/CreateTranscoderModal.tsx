'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { X, Upload, Video } from 'lucide-react';
import { Portal } from '@/components/ui/portal';

interface CreateTranscoderModalProps {
  open: boolean;
  onClose: () => void;
}

export function CreateTranscoderModal({ open, onClose }: CreateTranscoderModalProps) {
  const [pipelineName, setPipelineName] = useState('');
  const [outputQuality, setOutputQuality] = useState<string>('720p');
  const [generateMultiple, setGenerateMultiple] = useState(true);
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
      console.log('Creating Transcoder pipeline:', {
        name: pipelineName,
        file: selectedFile,
        settings: {
          outputQuality,
          generateMultiple,
        },
      });

      await new Promise(resolve => setTimeout(resolve, 1000));

      alert('Transcoder pipeline created successfully!');
      onClose();
      setPipelineName('');
      setSelectedFile(null);
      setOutputQuality('720p');
      setGenerateMultiple(true);
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
            <div className="p-2 bg-purple-100 rounded-lg">
              <Video className="h-5 w-5 text-purple-600" />
            </div>
            <CardTitle>Create Transcoder</CardTitle>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>

        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="name">Pipeline Name</Label>
            <Input
              id="name"
              placeholder="e.g., HD Mobile Streaming"
              value={pipelineName}
              onChange={(e) => setPipelineName(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="file">Video File</Label>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-gray-400 transition-colors relative">
              <Upload className="mx-auto h-8 w-8 text-gray-400 mb-2" />
              <div className="space-y-1">
                <p className="text-sm font-medium">Click to upload video file</p>
                <p className="text-xs text-muted-foreground">MP4, MOV, AVI up to 2GB</p>
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

          <div className="space-y-4">
            <h3 className="text-lg font-medium">Settings</h3>

            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="quality">Output Quality</Label>
                <Select value={outputQuality} onValueChange={setOutputQuality}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="360p">360p - Mobile Optimized</SelectItem>
                    <SelectItem value="480p">480p - Standard Mobile</SelectItem>
                    <SelectItem value="720p">720p - HD Mobile</SelectItem>
                    <SelectItem value="1080p">1080p - Full HD</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center space-x-2">
                <Checkbox
                  id="multiple"
                  checked={generateMultiple}
                  onCheckedChange={(checked) => setGenerateMultiple(checked as boolean)}
                />
                <Label htmlFor="multiple" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                  Generate multiple quality versions for adaptive streaming
                </Label>
              </div>

              {generateMultiple && (
                <div className="bg-blue-50 p-4 rounded-lg">
                  <p className="text-sm text-blue-700">
                    <strong>Multi-quality output:</strong> Will generate optimized versions at 360p, 480p, and your selected quality for adaptive streaming on Indian networks.
                  </p>
                </div>
              )}
            </div>
          </div>

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