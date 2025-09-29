'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { CheckCircle2, Clock, Settings, FileText, Video, Headphones, Image, Subtitles, Mic, BarChart, LucideIcon } from 'lucide-react';
import { PipelineFormData } from '../page';

interface ReviewStepProps {
  formData: PipelineFormData;
}

const SERVICE_DETAILS: Record<string, { name: string; icon: LucideIcon; description: string }> = {
  media_inspector: { name: 'Media Inspector', icon: FileText, description: 'Extract metadata and validate files' },
  video_processor: { name: 'Video Processor', icon: Video, description: 'Process and convert video' },
  audio_extractor: { name: 'Audio Extractor', icon: Headphones, description: 'Extract and process audio' },
  thumbnail_generator: { name: 'Thumbnail Generator', icon: Image, description: 'Generate thumbnails' },
  subtitle_generator: { name: 'Subtitle Generator', icon: Subtitles, description: 'Generate subtitles' },
  dubbing_generator: { name: 'Dubbing Generator', icon: Mic, description: 'Generate voice dubbing' },
  transcoder: { name: 'Transcoder', icon: Settings, description: 'Convert video formats' },
  scene_analyzer: { name: 'Scene Analyzer', icon: BarChart, description: 'Analyze scenes' },
  script_evaluator: { name: 'Script Evaluator', icon: BarChart, description: 'Evaluate content' },
};

export function ReviewStep({ formData }: ReviewStepProps) {
  const formatDuration = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  };

  const getParameterValue = (key: string, value: unknown) => {
    if (value === undefined || value === null || value === '') {
      return 'Not set';
    }
    if (typeof value === 'boolean') {
      return value ? 'Enabled' : 'Disabled';
    }
    return value.toString();
  };

  return (
    <div className="space-y-6">
      {/* Pipeline Summary */}
      <Card className="border-green-200 bg-green-50/50">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-green-800">
            <CheckCircle2 className="h-5 w-5" />
            Pipeline Ready for Creation
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">Name</p>
              <p className="font-medium">{formData.name}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Category</p>
              <Badge variant="outline">{formData.category}</Badge>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Estimated Duration</p>
              <div className="flex items-center gap-1">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">
                  {formData.estimatedDuration ? formatDuration(formData.estimatedDuration) : 'Calculating...'}
                </span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Basic Information */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Basic Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-sm text-muted-foreground mb-1">Name</p>
            <p className="font-medium">{formData.name}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground mb-1">Description</p>
            <p className="text-sm">{formData.description}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground mb-1">Category</p>
            <Badge variant="outline">{formData.category}</Badge>
          </div>
        </CardContent>
      </Card>

      {/* Pipeline Steps */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Pipeline Steps ({formData.steps.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {formData.steps.map((step, index) => {
              const serviceDetail = SERVICE_DETAILS[step.serviceName];
              const Icon = serviceDetail?.icon || Settings;

              return (
                <div key={index} className="flex items-center space-x-4 p-3 border rounded-lg">
                  <div className="w-8 h-8 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm font-medium">
                    {step.order}
                  </div>
                  <div className="p-2 bg-muted rounded-md">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="flex-1">
                    <p className="font-medium">{serviceDetail?.name || step.serviceName}</p>
                    <p className="text-sm text-muted-foreground">{serviceDetail?.description || step.topic}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-muted-foreground">Topic</p>
                    <p className="text-xs font-mono">{step.topic}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Default Parameters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Default Parameters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Video Parameters */}
          {(formData.defaultParameters.resolution ||
            formData.defaultParameters.videoCodec ||
            formData.defaultParameters.chunkDuration ||
            formData.defaultParameters.videoBitrate) && (
            <div>
              <h4 className="font-medium mb-3 flex items-center gap-2">
                <Video className="h-4 w-4" />
                Video Processing
              </h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">Resolution</p>
                  <p className="font-medium">{getParameterValue('resolution', formData.defaultParameters.resolution)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Codec</p>
                  <p className="font-medium">{getParameterValue('videoCodec', formData.defaultParameters.videoCodec)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Chunk Duration</p>
                  <p className="font-medium">{getParameterValue('chunkDuration', formData.defaultParameters.chunkDuration)}s</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Bitrate</p>
                  <p className="font-medium">{getParameterValue('videoBitrate', formData.defaultParameters.videoBitrate)} kbps</p>
                </div>
              </div>
            </div>
          )}

          {/* Audio Parameters */}
          {(formData.defaultParameters.audioCodec ||
            formData.defaultParameters.audioBitrate ||
            formData.defaultParameters.sampleRate ||
            formData.defaultParameters.channels) && (
            <>
              <Separator />
              <div>
                <h4 className="font-medium mb-3 flex items-center gap-2">
                  <Headphones className="h-4 w-4" />
                  Audio Processing
                </h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <p className="text-muted-foreground">Codec</p>
                    <p className="font-medium">{getParameterValue('audioCodec', formData.defaultParameters.audioCodec)}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Bitrate</p>
                    <p className="font-medium">{getParameterValue('audioBitrate', formData.defaultParameters.audioBitrate)} kbps</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Sample Rate</p>
                    <p className="font-medium">{getParameterValue('sampleRate', formData.defaultParameters.sampleRate)} Hz</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Channels</p>
                    <p className="font-medium">{getParameterValue('channels', formData.defaultParameters.channels)}</p>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Analysis Parameters */}
          {(formData.defaultParameters.analysisDepth ||
            formData.defaultParameters.sceneDetection ||
            formData.defaultParameters.objectDetection ||
            formData.defaultParameters.speechRecognition ||
            formData.defaultParameters.emotionAnalysis) && (
            <>
              <Separator />
              <div>
                <h4 className="font-medium mb-3 flex items-center gap-2">
                  <BarChart className="h-4 w-4" />
                  Analysis Settings
                </h4>
                <div className="space-y-3">
                  <div>
                    <p className="text-muted-foreground text-sm">Analysis Depth</p>
                    <p className="font-medium">{getParameterValue('analysisDepth', formData.defaultParameters.analysisDepth)}</p>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div className="flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${formData.defaultParameters.sceneDetection ? 'bg-green-500' : 'bg-gray-300'}`} />
                      <span>Scene Detection</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${formData.defaultParameters.objectDetection ? 'bg-green-500' : 'bg-gray-300'}`} />
                      <span>Object Detection</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${formData.defaultParameters.speechRecognition ? 'bg-green-500' : 'bg-gray-300'}`} />
                      <span>Speech Recognition</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${formData.defaultParameters.emotionAnalysis ? 'bg-green-500' : 'bg-gray-300'}`} />
                      <span>Emotion Analysis</span>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Custom Parameters */}
          {formData.defaultParameters.customParameters &&
           Object.keys(formData.defaultParameters.customParameters).length > 0 && (
            <>
              <Separator />
              <div>
                <h4 className="font-medium mb-3 flex items-center gap-2">
                  <Settings className="h-4 w-4" />
                  Custom Parameters
                </h4>
                <div className="space-y-2">
                  {Object.entries(formData.defaultParameters.customParameters).map(([key, value]) => (
                    <div key={key} className="flex justify-between items-center text-sm">
                      <span className="text-muted-foreground">{key}</span>
                      <span className="font-medium">{String(value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* No parameters set */}
          {!Object.keys(formData.defaultParameters).some((key) => {
            const value = formData.defaultParameters[key as keyof typeof formData.defaultParameters];
            return value !== undefined && value !== null && String(value) !== '';
          }) && (
            <div className="text-center py-8">
              <Settings className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">No default parameters configured</p>
              <p className="text-xs text-muted-foreground">Parameters can be set when running executions</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}