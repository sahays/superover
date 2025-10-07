'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Eye, Plus, Play, Settings, Download, Calendar, Clock, MoreVertical, FileText } from 'lucide-react';
import { CreateSceneAnalyzerModal } from './components/CreateSceneAnalyzerModal';
import { ViewSettingsModal } from './components/ViewSettingsModal';
import { ViewOutputsModal } from './components/ViewOutputsModal';

// Mock data for existing pipelines
const mockSceneAnalyzerPipelines = [
  {
    id: '1',
    name: 'Movie Trailer Analysis',
    createdAt: '2024-01-15',
    lastRun: '2024-01-20',
    status: 'completed' as const,
    settings: {
      compressionRate: '720p' as const,
      chunkLength: 30,
    },
    outputs: [
      { id: '1', name: 'video_chunks.zip', size: '45.2 MB', type: 'video chunks' },
      { id: '2', name: 'analysis_report.json', size: '2.1 MB', type: 'analysis report' },
    ],
  },
  {
    id: '2',
    name: 'Educational Content Review',
    createdAt: '2024-01-18',
    lastRun: null,
    status: 'draft' as const,
    settings: {
      compressionRate: '480p' as const,
      chunkLength: 60,
    },
    outputs: [],
  },
  {
    id: '3',
    name: 'Advertisement Breakdown',
    createdAt: '2024-01-20',
    lastRun: '2024-01-22',
    status: 'running' as const,
    settings: {
      compressionRate: '1080p' as const,
      chunkLength: 15,
    },
    outputs: [],
  },
];

export default function SceneAnalyzerPage() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedPipeline, setSelectedPipeline] = useState<string | null>(null);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showOutputsModal, setShowOutputsModal] = useState(false);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'running':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'draft':
        return 'bg-gray-100 text-gray-800 border-gray-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const handleViewSettings = (pipelineId: string) => {
    setSelectedPipeline(pipelineId);
    setShowSettingsModal(true);
  };

  const handleViewOutputs = (pipelineId: string) => {
    setSelectedPipeline(pipelineId);
    setShowOutputsModal(true);
  };

  const selectedPipelineData = selectedPipeline
    ? mockSceneAnalyzerPipelines.find(p => p.id === selectedPipeline)
    : null;

  return (
    <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Eye className="h-6 w-6 text-blue-600" />
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold">Scene Analyzer</h1>
            </div>
            <p className="text-muted-foreground">
              Analyze video content scene-by-scene with optional compression
            </p>
          </div>
          <Button
            onClick={() => setShowCreateModal(true)}
            className="w-full sm:w-auto"
          >
            <Plus className="h-4 w-4 mr-2" />
            Create New
          </Button>
        </div>

        {/* Pipeline Cards */}
        {mockSceneAnalyzerPipelines.length === 0 ? (
          <Card className="text-center py-12">
            <CardContent>
              <Eye className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No scene analyzers yet</h3>
              <p className="text-muted-foreground mb-4">
                Create your first scene analyzer to get started
              </p>
              <Button onClick={() => setShowCreateModal(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Create New
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {mockSceneAnalyzerPipelines.map((pipeline) => (
              <Card key={pipeline.id} className="hover:shadow-md transition-shadow flex flex-col">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <CardTitle className="text-lg font-semibold truncate">
                        {pipeline.name}
                      </CardTitle>
                      <Badge variant="outline" className={`${getStatusColor(pipeline.status)} mt-2 w-fit`}>
                        {pipeline.status}
                      </Badge>
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => handleViewSettings(pipeline.id)}>
                          <Settings className="h-4 w-4 mr-2" />
                          Settings
                        </DropdownMenuItem>
                        {pipeline.status === 'completed' && (
                          <DropdownMenuItem onClick={() => handleViewOutputs(pipeline.id)}>
                            <Download className="h-4 w-4 mr-2" />
                            Outputs
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </CardHeader>

                <CardContent className="pt-0 flex-1 flex flex-col">
                  <div className="space-y-3 flex-1">
                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        <span>Created {pipeline.createdAt}</span>
                      </div>
                    </div>

                    {pipeline.lastRun && (
                      <div className="flex items-center gap-1 text-sm text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        <span>Last run {pipeline.lastRun}</span>
                      </div>
                    )}
                  </div>

                  <div className="flex justify-end pt-3 mt-auto">
                    {pipeline.status === 'completed' ? (
                      <Button
                        size="sm"
                        onClick={() => handleViewOutputs(pipeline.id)}
                      >
                        <FileText className="h-3 w-3 mr-1" />
                        See Analysis
                      </Button>
                    ) : pipeline.status === 'running' ? (
                      <Button
                        size="sm"
                        disabled
                      >
                        <Play className="h-3 w-3 mr-1" />
                        Running...
                      </Button>
                    ) : (
                      <Button size="sm">
                        <Play className="h-3 w-3 mr-1" />
                        Run
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Modals */}
        <CreateSceneAnalyzerModal
          open={showCreateModal}
          onClose={() => setShowCreateModal(false)}
        />

        {selectedPipelineData && (
          <>
            <ViewSettingsModal
              open={showSettingsModal}
              onClose={() => setShowSettingsModal(false)}
              pipeline={selectedPipelineData}
            />

            <ViewOutputsModal
              open={showOutputsModal}
              onClose={() => setShowOutputsModal(false)}
              pipeline={selectedPipelineData}
            />
          </>
        )}
    </div>
  );
}