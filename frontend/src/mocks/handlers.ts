import { http, HttpResponse } from 'msw';
import {
  mockFiles,
  mockPipelines,
  mockJobs,
  mockExecutions,
  mockOutputFiles,
  mockAnalysisResults
} from './data';
import { PaginatedResponse } from '@/types';

// Helper function to create paginated responses
function createPaginatedResponse<T>(
  data: T[],
  page: number = 1,
  limit: number = 10
): PaginatedResponse<T> {
  const start = (page - 1) * limit;
  const end = start + limit;
  const paginatedData = data.slice(start, end);
  const total = data.length;
  const totalPages = Math.ceil(total / limit);

  return {
    success: true,
    data: paginatedData,
    pagination: {
      page,
      limit,
      total,
      totalPages,
      hasNext: page < totalPages,
      hasPrev: page > 1,
    },
  };
}

// Helper function to simulate delays
const delay = (ms: number = 1000) => new Promise(resolve => setTimeout(resolve, ms));

export const handlers = [
  // Files API
  http.get('/api/files', async ({ request }) => {
    await delay(500);
    const url = new URL(request.url);
    const page = parseInt(url.searchParams.get('page') || '1');
    const limit = parseInt(url.searchParams.get('limit') || '10');
    const search = url.searchParams.get('search');
    const type = url.searchParams.get('type');
    const status = url.searchParams.get('status');

    let filteredFiles = mockFiles;

    if (search) {
      filteredFiles = filteredFiles.filter(file =>
        file.name.toLowerCase().includes(search.toLowerCase())
      );
    }

    if (type) {
      filteredFiles = filteredFiles.filter(file => file.type.includes(type));
    }

    if (status) {
      filteredFiles = filteredFiles.filter(file => file.status === status);
    }

    return HttpResponse.json(createPaginatedResponse(filteredFiles, page, limit));
  }),

  http.get('/api/files/:id', async ({ params }) => {
    await delay(300);
    const file = mockFiles.find(f => f.id === params.id);
    if (!file) {
      return HttpResponse.json(
        { success: false, error: 'File not found' },
        { status: 404 }
      );
    }
    return HttpResponse.json({ success: true, data: file });
  }),

  http.post('/api/files/upload', async ({ request }) => {
    await delay(1500);
    const formData = await request.formData();
    const file = formData.get('file') as File;

    if (!file) {
      return HttpResponse.json(
        { success: false, error: 'No file provided' },
        { status: 400 }
      );
    }

    const newFile = {
      id: `file-${Date.now()}`,
      name: file.name,
      size: file.size,
      type: file.type,
      gcsPath: `gs://super-over-alchemy/raw/${file.name}`,
      uploadedAt: new Date().toISOString(),
      status: 'uploaded' as const,
    };

    return HttpResponse.json({
      success: true,
      data: newFile,
      message: 'File uploaded successfully'
    });
  }),

  http.delete('/api/files/:id', async ({ params }) => {
    await delay(800);
    const fileExists = mockFiles.some(f => f.id === params.id);
    if (!fileExists) {
      return HttpResponse.json(
        { success: false, error: 'File not found' },
        { status: 404 }
      );
    }
    return HttpResponse.json({
      success: true,
      message: 'File deleted successfully'
    });
  }),

  // Pipelines API
  http.get('/api/workflows/pipelines', async () => {
    await delay(300);
    return HttpResponse.json({ success: true, data: mockPipelines });
  }),

  http.get('/api/workflows/pipelines/:id', async ({ params }) => {
    await delay(200);
    const pipeline = mockPipelines.find(p => p.id === params.id);
    if (!pipeline) {
      return HttpResponse.json(
        { success: false, error: 'Pipeline not found' },
        { status: 404 }
      );
    }
    return HttpResponse.json({ success: true, data: pipeline });
  }),

  // Executions API
  http.get('/api/executions', async ({ request }) => {
    await delay(500);
    const url = new URL(request.url);
    const page = parseInt(url.searchParams.get('page') || '1');
    const limit = parseInt(url.searchParams.get('limit') || '10');
    const status = url.searchParams.get('status');
    const pipelineId = url.searchParams.get('pipelineId');

    let filteredExecutions = mockExecutions;

    if (status) {
      filteredExecutions = filteredExecutions.filter(exec => exec.status === status);
    }

    if (pipelineId) {
      filteredExecutions = filteredExecutions.filter(exec => exec.pipelineId === pipelineId);
    }

    return HttpResponse.json(createPaginatedResponse(filteredExecutions, page, limit));
  }),

  http.get('/api/executions/:id', async ({ params }) => {
    await delay(300);
    const execution = mockExecutions.find(e => e.id === params.id);
    if (!execution) {
      return HttpResponse.json(
        { success: false, error: 'Execution not found' },
        { status: 404 }
      );
    }
    return HttpResponse.json({ success: true, data: execution });
  }),

  http.post('/api/executions', async ({ request }) => {
    await delay(1000);
    const body = await request.json() as Record<string, unknown>;

    const newExecution = {
      id: `exec-${Date.now()}`,
      jobId: `job-${Date.now()}`,
      pipelineId: body.pipelineId,
      pipelineName: mockPipelines.find(p => p.id === body.pipelineId)?.name || 'Unknown',
      sourceFileName: body.sourceFileName || 'unknown.file',
      status: 'pending' as const,
      startedAt: new Date().toISOString(),
      progress: {
        currentStep: 'initializing',
        completed: 0,
        total: mockPipelines.find(p => p.id === body.pipelineId)?.steps.length || 1,
        percentage: 0,
      },
      parameters: body.parameters || {},
      results: [],
      logs: [],
    };

    return HttpResponse.json({
      success: true,
      data: newExecution,
      message: 'Execution started successfully'
    });
  }),

  http.post('/api/executions/:id/retry', async ({ params }) => {
    await delay(800);
    const execution = mockExecutions.find(e => e.id === params.id);
    if (!execution) {
      return HttpResponse.json(
        { success: false, error: 'Execution not found' },
        { status: 404 }
      );
    }

    const retriedExecution = {
      ...execution,
      id: `exec-${Date.now()}-retry`,
      status: 'pending' as const,
      startedAt: new Date().toISOString(),
      completedAt: undefined,
      progress: {
        currentStep: 'initializing',
        completed: 0,
        total: execution.progress.total,
        percentage: 0,
      },
      error: undefined,
    };

    return HttpResponse.json({
      success: true,
      data: retriedExecution,
      message: 'Execution retry started'
    });
  }),

  http.post('/api/executions/:id/cancel', async ({ params }) => {
    await delay(500);
    const execution = mockExecutions.find(e => e.id === params.id);
    if (!execution) {
      return HttpResponse.json(
        { success: false, error: 'Execution not found' },
        { status: 404 }
      );
    }

    return HttpResponse.json({
      success: true,
      message: 'Execution cancelled successfully'
    });
  }),

  // Real-time updates endpoint (SSE simulation)
  http.get('/api/executions/:id/stream', async ({ params }) => {
    // This would typically be handled by SSE, but for demo purposes
    // we'll return the current execution status
    await delay(200);
    const execution = mockExecutions.find(e => e.id === params.id);
    if (!execution) {
      return HttpResponse.json(
        { success: false, error: 'Execution not found' },
        { status: 404 }
      );
    }
    return HttpResponse.json({ success: true, data: execution });
  }),

  // Outputs API
  http.get('/api/outputs', async ({ request }) => {
    await delay(400);
    const url = new URL(request.url);
    const page = parseInt(url.searchParams.get('page') || '1');
    const limit = parseInt(url.searchParams.get('limit') || '10');
    const executionId = url.searchParams.get('executionId');
    const fileType = url.searchParams.get('fileType');

    let filteredOutputs = mockOutputFiles;

    if (executionId) {
      filteredOutputs = filteredOutputs.filter(output => output.executionId === executionId);
    }

    if (fileType) {
      filteredOutputs = filteredOutputs.filter(output => output.fileType.includes(fileType));
    }

    return HttpResponse.json(createPaginatedResponse(filteredOutputs, page, limit));
  }),

  http.get('/api/outputs/:id', async ({ params }) => {
    await delay(200);
    const output = mockOutputFiles.find(o => o.id === params.id);
    if (!output) {
      return HttpResponse.json(
        { success: false, error: 'Output not found' },
        { status: 404 }
      );
    }
    return HttpResponse.json({ success: true, data: output });
  }),

  http.get('/api/outputs/:id/download', async ({ params }) => {
    await delay(300);
    const output = mockOutputFiles.find(o => o.id === params.id);
    if (!output) {
      return HttpResponse.json(
        { success: false, error: 'Output not found' },
        { status: 404 }
      );
    }

    // Return a download URL (in real implementation, this would be a signed GCS URL)
    return HttpResponse.json({
      success: true,
      data: {
        downloadUrl: output.downloadUrl,
        expiresAt: new Date(Date.now() + 3600000).toISOString() // 1 hour from now
      }
    });
  }),

  http.delete('/api/outputs/:id', async ({ params }) => {
    await delay(600);
    const outputExists = mockOutputFiles.some(o => o.id === params.id);
    if (!outputExists) {
      return HttpResponse.json(
        { success: false, error: 'Output not found' },
        { status: 404 }
      );
    }
    return HttpResponse.json({
      success: true,
      message: 'Output deleted successfully'
    });
  }),

  // Analysis Results API
  http.get('/api/outputs/:id/analysis', async ({ params }) => {
    await delay(400);
    const analysis = mockAnalysisResults.find(a => a.executionId === params.id);
    if (!analysis) {
      return HttpResponse.json(
        { success: false, error: 'Analysis not found' },
        { status: 404 }
      );
    }
    return HttpResponse.json({ success: true, data: analysis });
  }),

  // Jobs API (internal)
  http.get('/api/jobs', async ({ request }) => {
    await delay(300);
    const url = new URL(request.url);
    const page = parseInt(url.searchParams.get('page') || '1');
    const limit = parseInt(url.searchParams.get('limit') || '10');
    const status = url.searchParams.get('status');

    let filteredJobs = mockJobs;

    if (status) {
      filteredJobs = filteredJobs.filter(job => job.status === status);
    }

    return HttpResponse.json(createPaginatedResponse(filteredJobs, page, limit));
  }),

  http.get('/api/jobs/:id', async ({ params }) => {
    await delay(200);
    const job = mockJobs.find(j => j.id === params.id);
    if (!job) {
      return HttpResponse.json(
        { success: false, error: 'Job not found' },
        { status: 404 }
      );
    }
    return HttpResponse.json({ success: true, data: job });
  }),

  // Health check
  http.get('/api/health', async () => {
    return HttpResponse.json({
      success: true,
      data: {
        status: 'healthy',
        timestamp: new Date().toISOString()
      }
    });
  }),

  // Catch-all for unhandled requests
  http.all('*', ({ request }) => {
    console.warn(`Unhandled ${request.method} request to ${request.url}`);
    return HttpResponse.json(
      { success: false, error: 'API endpoint not found' },
      { status: 404 }
    );
  }),
];