'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Search, FileText, Video, Headphones, Image, Subtitles, Mic, Settings, BarChart } from 'lucide-react';
import { PipelineFormData } from '../page';

interface ServiceSelectionStepProps {
  formData: PipelineFormData;
  updateFormData: (updates: Partial<PipelineFormData>) => void;
}

const AVAILABLE_SERVICES = [
  {
    id: 'media_inspector',
    name: 'Media Inspector',
    description: 'Extract metadata and validate media files',
    category: 'core',
    icon: FileText,
    estimatedTime: '5-10 min',
    required: true,
  },
  {
    id: 'video_processor',
    name: 'Video Processor',
    description: 'Video chunking, scaling, and codec conversion',
    category: 'video',
    icon: Video,
    estimatedTime: '15-30 min',
  },
  {
    id: 'audio_extractor',
    name: 'Audio Extractor',
    description: 'Extract and process audio tracks',
    category: 'audio',
    icon: Headphones,
    estimatedTime: '10-20 min',
  },
  {
    id: 'thumbnail_generator',
    name: 'Thumbnail Generator',
    description: 'Generate video thumbnails and preview images',
    category: 'video',
    icon: Image,
    estimatedTime: '5-15 min',
  },
  {
    id: 'subtitle_generator',
    name: 'Subtitle Generator',
    description: 'Auto-generate subtitles and captions',
    category: 'content',
    icon: Subtitles,
    estimatedTime: '20-40 min',
  },
  {
    id: 'dubbing_generator',
    name: 'Dubbing Generator',
    description: 'Voice synthesis and multi-language dubbing',
    category: 'content',
    icon: Mic,
    estimatedTime: '30-60 min',
  },
  {
    id: 'transcoder',
    name: 'Transcoder',
    description: 'Multi-format conversion and streaming prep',
    category: 'video',
    icon: Settings,
    estimatedTime: '20-45 min',
  },
  {
    id: 'scene_analyzer',
    name: 'Scene Analyzer',
    description: 'Scene detection and content analysis',
    category: 'analysis',
    icon: BarChart,
    estimatedTime: '25-50 min',
  },
  {
    id: 'script_evaluator',
    name: 'Script Evaluator',
    description: 'Content scoring and compliance checking',
    category: 'analysis',
    icon: BarChart,
    estimatedTime: '15-30 min',
  },
];

const CATEGORY_COLORS: Record<string, string> = {
  core: 'bg-blue-100 text-blue-800 border-blue-200',
  video: 'bg-purple-100 text-purple-800 border-purple-200',
  audio: 'bg-green-100 text-green-800 border-green-200',
  content: 'bg-orange-100 text-orange-800 border-orange-200',
  analysis: 'bg-yellow-100 text-yellow-800 border-yellow-200',
};

export function ServiceSelectionStep({ formData, updateFormData }: ServiceSelectionStepProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  const filteredServices = AVAILABLE_SERVICES.filter(service => {
    const matchesSearch = service.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      service.description.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = selectedCategory === 'all' || service.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const handleServiceToggle = (serviceId: string, checked: boolean) => {
    const currentServices = formData.selectedServices;
    const updatedServices = checked
      ? [...currentServices, serviceId]
      : currentServices.filter(id => id !== serviceId);

    updateFormData({ selectedServices: updatedServices });
  };

  const categories = ['all', ...Array.from(new Set(AVAILABLE_SERVICES.map(s => s.category)))];

  return (
    <div className="space-y-6">
      {/* Search and Filter */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
          <Input
            placeholder="Search services..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          {categories.map(category => (
            <Badge
              key={category}
              variant={selectedCategory === category ? "default" : "outline"}
              className="cursor-pointer"
              onClick={() => setSelectedCategory(category)}
            >
              {category === 'all' ? 'All' : category.charAt(0).toUpperCase() + category.slice(1)}
            </Badge>
          ))}
        </div>
      </div>

      {/* Selected Services Summary */}
      {formData.selectedServices.length > 0 && (
        <Card className="bg-muted/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Selected Services ({formData.selectedServices.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {formData.selectedServices.map(serviceId => {
                const service = AVAILABLE_SERVICES.find(s => s.id === serviceId);
                return service ? (
                  <Badge key={serviceId} variant="secondary">
                    {service.name}
                  </Badge>
                ) : null;
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Service Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredServices.map(service => {
          const Icon = service.icon;
          const isSelected = formData.selectedServices.includes(service.id);
          const isRequired = service.required;

          return (
            <Card
              key={service.id}
              className={`cursor-pointer transition-all hover:shadow-md ${
                isSelected ? 'ring-2 ring-primary bg-primary/5' : ''
              } ${isRequired ? 'border-blue-200 bg-blue-50/50' : ''}`}
              onClick={() => !isRequired && handleServiceToggle(service.id, !isSelected)}
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 bg-muted rounded-md">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <CardTitle className="text-base">{service.name}</CardTitle>
                      <Badge variant="outline" className={CATEGORY_COLORS[service.category]}>
                        {service.category}
                      </Badge>
                    </div>
                  </div>
                  <Checkbox
                    checked={isSelected || isRequired}
                    disabled={isRequired}
                    onCheckedChange={(checked) => handleServiceToggle(service.id, checked as boolean)}
                    onClick={(e) => e.stopPropagation()}
                  />
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <p className="text-sm text-muted-foreground mb-3">{service.description}</p>
                <div className="flex justify-between items-center text-xs">
                  <span className="text-muted-foreground">Est. Time: {service.estimatedTime}</span>
                  {isRequired && <Badge variant="secondary" className="text-xs">Required</Badge>}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {filteredServices.length === 0 && (
        <div className="text-center py-12">
          <Search className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-2 text-sm font-medium">No services found</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Try adjusting your search or category filter
          </p>
        </div>
      )}
    </div>
  );
}