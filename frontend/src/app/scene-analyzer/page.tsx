'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Eye, Plus, Settings, Download, Calendar, Clock, MoreVertical, FileText, Loader2 } from 'lucide-react';
import { CreateSceneAnalyzerModal } from './components/CreateSceneAnalyzerModal';
import { ViewSettingsModal } from './components/ViewSettingsModal';
import { ViewOutputsModal } from './components/ViewOutputsModal';
import { sceneAnalyzerApi, SceneAnalysisJob } from '@/lib/api/scene-analyzer';

export default function SceneAnalyzerPage() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [jobs, setJobs] = useState<SceneAnalysisJob[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showOutputsModal, setShowOutputsModal] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [pollingJobIds, setPollingJobIds] = useState<Set<string>>(new Set());

  // Load jobs from local storage on mount
  useEffect(() => {
    const savedJobs = localStorage.getItem('sceneAnalysisJobs');
    if (savedJobs) {
      try {
        const parsedJobs = JSON.parse(savedJobs);
        setJobs(parsedJobs);

        // Start polling for any non-terminal jobs
        parsedJobs.forEach((job: SceneAnalysisJob) => {
          if (job.status === 'queued' || job.status === 'processing') {
            startPollingJob(job.job_id);
          }
        });
      } catch (error) {
        console.error('Failed to load jobs from storage:', error);
      }
    }
    setIsLoading(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Save jobs to local storage whenever they change
  useEffect(() => {
    if (jobs.length > 0) {
      localStorage.setItem('sceneAnalysisJobs', JSON.stringify(jobs));
    }
  }, [jobs]);

  const startPollingJob = (jobId: string) => {
    if (pollingJobIds.has(jobId)) return; // Already polling

    setPollingJobIds(prev => new Set(prev).add(jobId));

    sceneAnalyzerApi.pollJobStatus(
      jobId,
      (updatedJob) => {
        // Update job in list
        setJobs(prev => prev.map(job =>
          job.job_id === jobId ? updatedJob : job
        ));
      },
      5000 // Poll every 5 seconds
    )
    .then((completedJob) => {
      // Job completed successfully
      console.log('Job completed:', completedJob);
      setPollingJobIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(jobId);
        return newSet;
      });
    })
    .catch((error) => {
      // Job failed or polling error
      console.error('Job polling error:', error);
      setPollingJobIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(jobId);
        return newSet;
      });
    });
  };

  const handleJobCreated = async (jobId: string) => {
    // Fetch the newly created job
    try {
      const job = await sceneAnalyzerApi.getJobStatus(jobId);
      setJobs(prev => [job, ...prev]);

      // Start polling for this job
      startPollingJob(jobId);
    } catch (error) {
      console.error('Failed to fetch job status:', error);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'processing':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'queued':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'failed':
        return 'bg-red-100 text-red-800 border-red-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const handleViewSettings = (jobId: string) => {
    setSelectedJobId(jobId);
    setShowSettingsModal(true);
  };

  const handleViewOutputs = (jobId: string) => {
    setSelectedJobId(jobId);
    setShowOutputsModal(true);
  };

  const selectedJob = selectedJobId
    ? jobs.find(j => j.job_id === selectedJobId)
    : null;

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleDateString();
    } catch {
      return dateString;
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

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
            Analyze video content scene-by-scene with AI-powered insights
          </p>
        </div>
        <Button
          onClick={() => setShowCreateModal(true)}
          className="w-full sm:w-auto"
        >
          <Plus className="h-4 w-4 mr-2" />
          Create New Analysis
        </Button>
      </div>

      {/* Job Cards */}
      {jobs.length === 0 ? (
        <Card className="text-center py-12">
          <CardContent>
            <Eye className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No scene analyses yet</h3>
            <p className="text-muted-foreground mb-4">
              Upload a video to get started with AI-powered scene analysis
            </p>
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create New Analysis
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {jobs.map((job) => (
            <Card key={job.job_id} className="hover:shadow-md transition-shadow flex flex-col">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <CardTitle className="text-lg font-semibold truncate">
                      {job.gcs_path.split('/').pop() || 'Video Analysis'}
                    </CardTitle>
                    <Badge variant="outline" className={`${getStatusColor(job.status)} mt-2 w-fit flex items-center gap-1`}>
                      {(job.status === 'processing' || job.status === 'queued') && (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      )}
                      {job.status}
                    </Badge>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => handleViewSettings(job.job_id)}>
                        <Settings className="h-4 w-4 mr-2" />
                        Details
                      </DropdownMenuItem>
                      {job.status === 'completed' && (
                        <DropdownMenuItem onClick={() => handleViewOutputs(job.job_id)}>
                          <Download className="h-4 w-4 mr-2" />
                          Results
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
                      <span>Created {formatDate(job.created_at)}</span>
                    </div>
                  </div>

                  {job.worker_start_time && (
                    <div className="flex items-center gap-1 text-sm text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      <span>Started {formatDate(job.worker_start_time)}</span>
                    </div>
                  )}

                  {job.error && (
                    <div className="text-sm text-red-600 bg-red-50 p-2 rounded">
                      Error: {job.error}
                    </div>
                  )}
                </div>

                <div className="flex justify-end pt-3 mt-auto">
                  {job.status === 'completed' ? (
                    <Button
                      size="sm"
                      onClick={() => handleViewOutputs(job.job_id)}
                    >
                      <FileText className="h-3 w-3 mr-1" />
                      View Results
                    </Button>
                  ) : job.status === 'processing' || job.status === 'queued' ? (
                    <Button
                      size="sm"
                      disabled
                      variant="outline"
                    >
                      <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                      {job.status === 'queued' ? 'Queued...' : 'Processing...'}
                    </Button>
                  ) : job.status === 'failed' ? (
                    <Button
                      size="sm"
                      variant="destructive"
                      disabled
                    >
                      Failed
                    </Button>
                  ) : null}
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
        onJobCreated={handleJobCreated}
      />

      {selectedJob && (
        <>
          <ViewSettingsModal
            open={showSettingsModal}
            onClose={() => setShowSettingsModal(false)}
            pipeline={{
              id: selectedJob.job_id,
              name: selectedJob.gcs_path.split('/').pop() || 'Video Analysis',
              createdAt: formatDate(selectedJob.created_at),
              lastRun: selectedJob.worker_start_time ? formatDate(selectedJob.worker_start_time) : null,
              status: selectedJob.status === 'completed' ? 'completed' : selectedJob.status === 'processing' ? 'running' : 'draft',
              settings: {
                compressionRate: '720p' as const,
                chunkLength: 30,
              },
            }}
          />

          <ViewOutputsModal
            open={showOutputsModal}
            onClose={() => setShowOutputsModal(false)}
            pipeline={{
              id: selectedJob.job_id,
              name: selectedJob.gcs_path.split('/').pop() || 'Video Analysis',
              outputs: selectedJob.results_path ? [
                {
                  id: '1',
                  name: 'analysis_report.json',
                  size: 'N/A',
                  type: 'analysis report',
                  url: selectedJob.results_path,
                },
              ] : [],
            }}
          />
        </>
      )}
    </div>
  );
}
