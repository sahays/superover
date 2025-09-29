'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { GripVertical, ArrowUp, ArrowDown, Trash2, FileText, Video, Headphones, Image, Subtitles, Mic, Settings, BarChart, LucideIcon } from 'lucide-react';
import { PipelineFormData } from '../page';
import { PipelineStep } from '@/types';

interface StepConfigurationStepProps {
  formData: PipelineFormData;
  updateFormData: (updates: Partial<PipelineFormData>) => void;
}

const SERVICE_DETAILS: Record<string, { name: string; icon: LucideIcon; topic: string }> = {
  media_inspector: { name: 'Media Inspector', icon: FileText, topic: 'media_inspection_jobs' },
  video_processor: { name: 'Video Processor', icon: Video, topic: 'video_processing_jobs' },
  audio_extractor: { name: 'Audio Extractor', icon: Headphones, topic: 'audio_extraction_jobs' },
  thumbnail_generator: { name: 'Thumbnail Generator', icon: Image, topic: 'thumbnail_generation_jobs' },
  subtitle_generator: { name: 'Subtitle Generator', icon: Subtitles, topic: 'subtitle_generation_jobs' },
  dubbing_generator: { name: 'Dubbing Generator', icon: Mic, topic: 'dubbing_generation_jobs' },
  transcoder: { name: 'Transcoder', icon: Settings, topic: 'transcoding_jobs' },
  scene_analyzer: { name: 'Scene Analyzer', icon: BarChart, topic: 'scene_analysis_jobs' },
  script_evaluator: { name: 'Script Evaluator', icon: BarChart, topic: 'script_evaluation_jobs' },
};

export function StepConfigurationStep({ formData, updateFormData }: StepConfigurationStepProps) {
  const [steps, setSteps] = useState<PipelineStep[]>([]);

  // Initialize steps from selected services
  useEffect(() => {
    if (formData.selectedServices.length > 0 && steps.length === 0) {
      const initialSteps: PipelineStep[] = formData.selectedServices.map((serviceId, index) => ({
        order: index + 1,
        serviceName: serviceId,
        topic: SERVICE_DETAILS[serviceId]?.topic || `${serviceId}_jobs`,
        parameters: {},
      }));
      setSteps(initialSteps);
      updateFormData({ steps: initialSteps });
    }
  }, [formData.selectedServices, steps.length, updateFormData]);

  const moveStep = (index: number, direction: 'up' | 'down') => {
    const newSteps = [...steps];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;

    if (targetIndex >= 0 && targetIndex < newSteps.length) {
      [newSteps[index], newSteps[targetIndex]] = [newSteps[targetIndex], newSteps[index]];

      // Update order numbers
      newSteps.forEach((step, idx) => {
        step.order = idx + 1;
      });

      setSteps(newSteps);
      updateFormData({ steps: newSteps });
    }
  };

  const removeStep = (index: number) => {
    const newSteps = steps.filter((_, idx) => idx !== index);

    // Update order numbers
    newSteps.forEach((step, idx) => {
      step.order = idx + 1;
    });

    setSteps(newSteps);

    // Also update selected services
    const updatedServices = formData.selectedServices.filter(
      service => service !== steps[index].serviceName
    );

    updateFormData({
      steps: newSteps,
      selectedServices: updatedServices
    });
  };

  const updateStepParameter = (stepIndex: number, key: string, value: string) => {
    const newSteps = [...steps];
    if (!newSteps[stepIndex].parameters) {
      newSteps[stepIndex].parameters = {};
    }
    newSteps[stepIndex].parameters![key] = value;

    setSteps(newSteps);
    updateFormData({ steps: newSteps });
  };

  const calculateEstimatedDuration = useCallback(() => {
    // Base time estimates in seconds for each service
    const serviceTimings: Record<string, number> = {
      media_inspector: 300, // 5 min
      video_processor: 1800, // 30 min
      audio_extractor: 900, // 15 min
      thumbnail_generator: 600, // 10 min
      subtitle_generator: 2400, // 40 min
      dubbing_generator: 3600, // 60 min
      transcoder: 2700, // 45 min
      scene_analyzer: 3000, // 50 min
      script_evaluator: 1800, // 30 min
    };

    const totalTime = steps.reduce((total, step) => {
      return total + (serviceTimings[step.serviceName] || 900);
    }, 0);

    return totalTime;
  }, [steps]);

  useEffect(() => {
    if (steps.length > 0) {
      const totalTime = calculateEstimatedDuration();
      updateFormData({ estimatedDuration: totalTime });
    }
  }, [steps, calculateEstimatedDuration, updateFormData]);

  const formatDuration = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  };

  return (
    <div className="space-y-6">
      {/* Pipeline Overview */}
      <Card className="bg-muted/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Pipeline Overview</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Total Steps:</span>
              <span className="ml-2 font-medium">{steps.length}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Estimated Duration:</span>
              <span className="ml-2 font-medium">
                {formData.estimatedDuration ? formatDuration(formData.estimatedDuration) : 'Calculating...'}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Category:</span>
              <Badge variant="outline" className="ml-2">
                {formData.category}
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Step Configuration */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium">Configure Steps</h3>
          <p className="text-sm text-muted-foreground">
            Drag to reorder • Configure parameters for each step
          </p>
        </div>

        {steps.length === 0 ? (
          <Card className="text-center py-12">
            <CardContent>
              <Settings className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No services selected</h3>
              <p className="text-muted-foreground">
                Go back to the previous step to select services for your pipeline.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {steps.map((step, index) => {
              const serviceDetail = SERVICE_DETAILS[step.serviceName];
              const Icon = serviceDetail?.icon || Settings;

              return (
                <Card key={`${step.serviceName}-${index}`} className="border-l-4 border-l-primary">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="flex items-center space-x-2">
                          <GripVertical className="h-4 w-4 text-muted-foreground cursor-grab" />
                          <div className="w-8 h-8 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm font-medium">
                            {step.order}
                          </div>
                        </div>
                        <div className="p-2 bg-muted rounded-md">
                          <Icon className="h-4 w-4" />
                        </div>
                        <div>
                          <CardTitle className="text-base">{serviceDetail?.name || step.serviceName}</CardTitle>
                          <p className="text-sm text-muted-foreground">Topic: {step.topic}</p>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => moveStep(index, 'up')}
                          disabled={index === 0}
                        >
                          <ArrowUp className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => moveStep(index, 'down')}
                          disabled={index === steps.length - 1}
                        >
                          <ArrowDown className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeStep(index)}
                          disabled={step.serviceName === 'media_inspector'} // Don't allow removing required service
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </CardHeader>

                  <CardContent className="pt-0">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor={`priority-${index}`}>Priority</Label>
                        <Input
                          id={`priority-${index}`}
                          placeholder="e.g., high, medium, low"
                          value={String(step.parameters?.priority || '')}
                          onChange={(e) => updateStepParameter(index, 'priority', e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor={`timeout-${index}`}>Timeout (minutes)</Label>
                        <Input
                          id={`timeout-${index}`}
                          type="number"
                          placeholder="60"
                          value={String(step.parameters?.timeout || '')}
                          onChange={(e) => updateStepParameter(index, 'timeout', e.target.value)}
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Execution Flow Visualization */}
      {steps.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Execution Flow</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-center gap-2">
              {steps.map((step, index) => (
                <div key={index} className="flex items-center">
                  <div className="px-3 py-1 bg-primary text-primary-foreground rounded-md text-sm">
                    {step.order}. {SERVICE_DETAILS[step.serviceName]?.name || step.serviceName}
                  </div>
                  {index < steps.length - 1 && (
                    <div className="mx-2 text-muted-foreground">→</div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}