'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { ArrowLeft, ArrowRight, Check } from 'lucide-react';
import { BasicInfoStep } from './components/BasicInfoStep';
import { ServiceSelectionStep } from './components/ServiceSelectionStep';
import { StepConfigurationStep } from './components/StepConfigurationStep';
import { ParameterDefaultsStep } from './components/ParameterDefaultsStep';
import { ReviewStep } from './components/ReviewStep';
import { PipelineStep, WorkflowParameters } from '@/types';

const STEPS = [
  { id: 1, title: 'Basic Info', description: 'Pipeline name and description' },
  { id: 2, title: 'Select Services', description: 'Choose processing services' },
  { id: 3, title: 'Configure Steps', description: 'Order and configure services' },
  { id: 4, title: 'Default Parameters', description: 'Set default processing options' },
  { id: 5, title: 'Review', description: 'Review and create pipeline' },
];

export interface PipelineFormData {
  name: string;
  description: string;
  category: 'video' | 'audio' | 'analysis' | 'full';
  selectedServices: string[];
  steps: PipelineStep[];
  defaultParameters: WorkflowParameters;
  estimatedDuration?: number;
}

export default function CreatePipelinePage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState<PipelineFormData>({
    name: '',
    description: '',
    category: 'video',
    selectedServices: [],
    steps: [],
    defaultParameters: {},
  });

  const updateFormData = useCallback((updates: Partial<PipelineFormData>) => {
    setFormData(prev => ({ ...prev, ...updates }));
  }, []);

  const nextStep = () => {
    if (currentStep < STEPS.length) {
      setCurrentStep(currentStep + 1);
    }
  };

  const prevStep = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return formData.name.trim() && formData.description.trim();
      case 2:
        return formData.selectedServices.length > 0;
      case 3:
        return formData.steps.length > 0;
      case 4:
        return true; // Parameters are optional
      case 5:
        return true; // Review step
      default:
        return false;
    }
  };

  const handleSubmit = async () => {
    if (!canProceed() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      // Create the pipeline object
      const newPipeline = {
        name: formData.name,
        description: formData.description,
        category: formData.category,
        steps: formData.steps,
        defaultParameters: formData.defaultParameters,
        estimatedDuration: formData.estimatedDuration,
        status: 'draft' as const,
      };

      // TODO: Replace with actual API call
      console.log('Creating pipeline:', newPipeline);

      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Show success and redirect
      alert('Pipeline created successfully!');
      router.push('/pipelines');
    } catch (error) {
      console.error('Failed to create pipeline:', error);
      alert('Failed to create pipeline. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return <BasicInfoStep formData={formData} updateFormData={updateFormData} />;
      case 2:
        return <ServiceSelectionStep formData={formData} updateFormData={updateFormData} />;
      case 3:
        return <StepConfigurationStep formData={formData} updateFormData={updateFormData} />;
      case 4:
        return <ParameterDefaultsStep formData={formData} updateFormData={updateFormData} />;
      case 5:
        return <ReviewStep formData={formData} />;
      default:
        return null;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => window.history.back()}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Pipelines
          </Button>
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold">Create Pipeline</h1>
            <p className="text-muted-foreground">Build a custom media processing workflow</p>
          </div>
        </div>

        {/* Progress Indicator */}
        <Card>
          <CardContent className="p-6">
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium">Step {currentStep} of {STEPS.length}</span>
                <span className="text-sm text-muted-foreground">{Math.round((currentStep / STEPS.length) * 100)}% Complete</span>
              </div>
              <Progress value={(currentStep / STEPS.length) * 100} className="h-2" />

              {/* Step indicators */}
              <div className="flex justify-between">
                {STEPS.map((step) => (
                  <div
                    key={step.id}
                    className={`flex flex-col items-center space-y-2 flex-1 ${
                      step.id <= currentStep ? 'text-primary' : 'text-muted-foreground'
                    }`}
                  >
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                        step.id < currentStep
                          ? 'bg-primary text-primary-foreground'
                          : step.id === currentStep
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted text-muted-foreground'
                      }`}
                    >
                      {step.id < currentStep ? <Check className="h-4 w-4" /> : step.id}
                    </div>
                    <div className="text-center">
                      <div className="text-xs font-medium">{step.title}</div>
                      <div className="text-xs text-muted-foreground hidden sm:block">{step.description}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Step Content */}
        <Card>
          <CardHeader>
            <CardTitle>{STEPS[currentStep - 1].title}</CardTitle>
          </CardHeader>
          <CardContent>
            {renderStepContent()}
          </CardContent>
        </Card>

        {/* Navigation */}
        <div className="flex justify-between">
          <Button
            variant="outline"
            onClick={prevStep}
            disabled={currentStep === 1}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Previous
          </Button>

          {currentStep < STEPS.length ? (
            <Button
              onClick={nextStep}
              disabled={!canProceed()}
            >
              Next
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          ) : (
            <Button
              onClick={handleSubmit}
              disabled={!canProceed() || isSubmitting}
              className="bg-green-600 hover:bg-green-700"
            >
              {isSubmitting ? 'Creating...' : 'Create Pipeline'}
              <Check className="h-4 w-4 ml-2" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}