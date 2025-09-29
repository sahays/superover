'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Video, Headphones, BarChart, Settings } from 'lucide-react';
import { PipelineFormData } from '../page';
import { WorkflowParameters } from '@/types';

interface ParameterDefaultsStepProps {
  formData: PipelineFormData;
  updateFormData: (updates: Partial<PipelineFormData>) => void;
}

export function ParameterDefaultsStep({ formData, updateFormData }: ParameterDefaultsStepProps) {
  const updateParameter = (key: keyof WorkflowParameters, value: unknown) => {
    const updatedParameters = {
      ...formData.defaultParameters,
      [key]: value,
    };
    updateFormData({ defaultParameters: updatedParameters });
  };

  const updateCustomParameter = (key: string, value: string) => {
    const customParams = formData.defaultParameters.customParameters || {};
    const updatedCustomParams = {
      ...customParams,
      [key]: value,
    };
    updateParameter('customParameters', updatedCustomParams);
  };

  const hasVideoServices = formData.selectedServices.some(service =>
    ['video_processor', 'thumbnail_generator', 'transcoder'].includes(service)
  );

  const hasAudioServices = formData.selectedServices.some(service =>
    ['audio_extractor', 'dubbing_generator'].includes(service)
  );

  const hasAnalysisServices = formData.selectedServices.some(service =>
    ['scene_analyzer', 'script_evaluator'].includes(service)
  );

  const hasContentServices = formData.selectedServices.some(service =>
    ['subtitle_generator', 'dubbing_generator'].includes(service)
  );

  return (
    <div className="space-y-6">
      {/* Overview */}
      <Card className="bg-muted/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Default Parameters</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            Set default parameters for your pipeline. These can be overridden when running executions.
          </p>
          <div className="flex flex-wrap gap-2">
            {hasVideoServices && <Badge variant="outline"><Video className="h-3 w-3 mr-1" />Video</Badge>}
            {hasAudioServices && <Badge variant="outline"><Headphones className="h-3 w-3 mr-1" />Audio</Badge>}
            {hasAnalysisServices && <Badge variant="outline"><BarChart className="h-3 w-3 mr-1" />Analysis</Badge>}
            {hasContentServices && <Badge variant="outline"><Settings className="h-3 w-3 mr-1" />Content</Badge>}
          </div>
        </CardContent>
      </Card>

      {/* Video Processing Parameters */}
      {hasVideoServices && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2">
              <Video className="h-5 w-5" />
              Video Processing
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="resolution">Resolution</Label>
                <Select
                  value={formData.defaultParameters.resolution || '1080p'}
                  onValueChange={(value: '480p' | '720p' | '1080p' | '4k') => updateParameter('resolution', value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select resolution" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="480p">480p (SD)</SelectItem>
                    <SelectItem value="720p">720p (HD)</SelectItem>
                    <SelectItem value="1080p">1080p (Full HD)</SelectItem>
                    <SelectItem value="4k">4K (Ultra HD)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="videoCodec">Video Codec</Label>
                <Select
                  value={formData.defaultParameters.videoCodec || 'h264'}
                  onValueChange={(value: 'h264' | 'h265' | 'vp9') => updateParameter('videoCodec', value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select codec" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="h264">H.264 (AVC)</SelectItem>
                    <SelectItem value="h265">H.265 (HEVC)</SelectItem>
                    <SelectItem value="vp9">VP9</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="chunkDuration">Chunk Duration (seconds)</Label>
                <Input
                  id="chunkDuration"
                  type="number"
                  placeholder="10"
                  value={formData.defaultParameters.chunkDuration || ''}
                  onChange={(e) => updateParameter('chunkDuration', parseInt(e.target.value) || undefined)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="videoBitrate">Video Bitrate (kbps)</Label>
                <Input
                  id="videoBitrate"
                  type="number"
                  placeholder="8000"
                  value={formData.defaultParameters.videoBitrate || ''}
                  onChange={(e) => updateParameter('videoBitrate', parseInt(e.target.value) || undefined)}
                />
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Audio Processing Parameters */}
      {hasAudioServices && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2">
              <Headphones className="h-5 w-5" />
              Audio Processing
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="audioCodec">Audio Codec</Label>
                <Select
                  value={formData.defaultParameters.audioCodec || 'aac'}
                  onValueChange={(value: 'aac' | 'flac' | 'mp3') => updateParameter('audioCodec', value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select codec" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="aac">AAC</SelectItem>
                    <SelectItem value="flac">FLAC</SelectItem>
                    <SelectItem value="mp3">MP3</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="audioBitrate">Audio Bitrate (kbps)</Label>
                <Input
                  id="audioBitrate"
                  type="number"
                  placeholder="128"
                  value={formData.defaultParameters.audioBitrate || ''}
                  onChange={(e) => updateParameter('audioBitrate', parseInt(e.target.value) || undefined)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="sampleRate">Sample Rate (Hz)</Label>
                <Select
                  value={formData.defaultParameters.sampleRate?.toString() || '44100'}
                  onValueChange={(value) => updateParameter('sampleRate', parseInt(value))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select sample rate" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="22050">22.05 kHz</SelectItem>
                    <SelectItem value="44100">44.1 kHz</SelectItem>
                    <SelectItem value="48000">48 kHz</SelectItem>
                    <SelectItem value="96000">96 kHz</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="channels">Channels</Label>
                <Select
                  value={formData.defaultParameters.channels?.toString() || '2'}
                  onValueChange={(value) => updateParameter('channels', parseInt(value))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select channels" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1">Mono</SelectItem>
                    <SelectItem value="2">Stereo</SelectItem>
                    <SelectItem value="6">5.1 Surround</SelectItem>
                    <SelectItem value="8">7.1 Surround</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Analysis Parameters */}
      {hasAnalysisServices && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2">
              <BarChart className="h-5 w-5" />
              Analysis Settings
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="analysisDepth">Analysis Depth</Label>
              <Select
                value={formData.defaultParameters.analysisDepth || 'basic'}
                onValueChange={(value: 'basic' | 'detailed' | 'comprehensive') => updateParameter('analysisDepth', value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select depth" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="basic">Basic</SelectItem>
                  <SelectItem value="detailed">Detailed</SelectItem>
                  <SelectItem value="comprehensive">Comprehensive</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Separator />

            <div className="space-y-4">
              <h4 className="font-medium">Detection Options</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="sceneDetection"
                    checked={formData.defaultParameters.sceneDetection || false}
                    onCheckedChange={(checked) => updateParameter('sceneDetection', checked)}
                  />
                  <Label htmlFor="sceneDetection">Scene Detection</Label>
                </div>

                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="objectDetection"
                    checked={formData.defaultParameters.objectDetection || false}
                    onCheckedChange={(checked) => updateParameter('objectDetection', checked)}
                  />
                  <Label htmlFor="objectDetection">Object Detection</Label>
                </div>

                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="speechRecognition"
                    checked={formData.defaultParameters.speechRecognition || false}
                    onCheckedChange={(checked) => updateParameter('speechRecognition', checked)}
                  />
                  <Label htmlFor="speechRecognition">Speech Recognition</Label>
                </div>

                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="emotionAnalysis"
                    checked={formData.defaultParameters.emotionAnalysis || false}
                    onCheckedChange={(checked) => updateParameter('emotionAnalysis', checked)}
                  />
                  <Label htmlFor="emotionAnalysis">Emotion Analysis</Label>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Custom Parameters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Custom Parameters
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Add custom parameters specific to your pipeline or services.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="customParam1">Parameter Name</Label>
              <Input
                id="customParam1"
                placeholder="e.g., quality_preset"
                value={Object.keys(formData.defaultParameters.customParameters || {})[0] || ''}
                onChange={(e) => {
                  const currentValue = Object.values(formData.defaultParameters.customParameters || {})[0] || '';
                  if (e.target.value) {
                    updateCustomParameter(e.target.value, String(currentValue));
                  }
                }}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="customValue1">Parameter Value</Label>
              <Input
                id="customValue1"
                placeholder="e.g., high"
                value={String(Object.values(formData.defaultParameters.customParameters || {})[0] || '')}
                onChange={(e) => {
                  const currentKey = Object.keys(formData.defaultParameters.customParameters || {})[0] || '';
                  if (currentKey) {
                    updateCustomParameter(currentKey, e.target.value);
                  }
                }}
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}