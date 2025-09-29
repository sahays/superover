'use client';

import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { PipelineFormData } from '../page';

interface BasicInfoStepProps {
  formData: PipelineFormData;
  updateFormData: (updates: Partial<PipelineFormData>) => void;
}

export function BasicInfoStep({ formData, updateFormData }: BasicInfoStepProps) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-2">
          <Label htmlFor="name">Pipeline Name</Label>
          <Input
            id="name"
            placeholder="e.g., Custom Video Processing"
            value={formData.name}
            onChange={(e) => updateFormData({ name: e.target.value })}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="category">Category</Label>
          <Select
            value={formData.category}
            onValueChange={(value: 'video' | 'audio' | 'analysis' | 'full') =>
              updateFormData({ category: value })
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="Select category" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="video">Video Processing</SelectItem>
              <SelectItem value="audio">Audio Processing</SelectItem>
              <SelectItem value="analysis">Analysis Only</SelectItem>
              <SelectItem value="full">Full Pipeline</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="description">Description</Label>
        <Textarea
          id="description"
          placeholder="Describe what this pipeline will do..."
          value={formData.description}
          onChange={(e) => updateFormData({ description: e.target.value })}
          rows={4}
        />
      </div>

      <div className="bg-muted/50 p-4 rounded-lg">
        <h4 className="font-medium mb-2">Category Guidelines</h4>
        <ul className="text-sm text-muted-foreground space-y-1">
          <li><strong>Video:</strong> Focus on video processing, transcoding, thumbnails</li>
          <li><strong>Audio:</strong> Audio extraction, dubbing, voice processing</li>
          <li><strong>Analysis:</strong> Content analysis, metadata extraction, evaluation</li>
          <li><strong>Full:</strong> Comprehensive processing including all media types</li>
        </ul>
      </div>
    </div>
  );
}