import { filesApi as filesApiClass } from './api/files';
import { workflowsApi as workflowsApiClass } from './api/workflows';
import { executionsApi as executionsApiClass } from './api/executions';
import { outputsApi as outputsApiClass } from './api/outputs';
import { Pipeline, ExecutionFilters, WorkflowParameters, FileFilters } from '@/types';

// Simple wrapper functions that match the component usage
export const workflowsApi = {
  getPipelines: () => workflowsApiClass.getPipelines(),
  getPipeline: (id: string) => workflowsApiClass.getPipeline(id),
  createPipeline: (data: { name: string; description: string; steps: unknown[] }) => workflowsApiClass.createWorkflow(data),
  updatePipeline: (id: string, data: Partial<Pipeline>) => workflowsApiClass.updateWorkflow(id, data),
  deletePipeline: (id: string) => workflowsApiClass.deleteWorkflow(id),
};

export const executionsApi = {
  getExecutions: (params?: {
    page?: number;
    limit?: number;
    filters?: ExecutionFilters;
  }) => executionsApiClass.getExecutions(params),
  getExecution: (id: string) => executionsApiClass.getExecution(id),
  createExecution: (data: {
    sourceFileId: string;
    pipelineId: string;
    parameters?: WorkflowParameters;
  }) => executionsApiClass.createExecution(data),
  controlExecution: (id: string, action: string) => {
    // Map actions to the appropriate API calls
    switch (action) {
      case 'pause':
      case 'resume':
      case 'cancel':
        // Use a generic control endpoint
        return fetch(`/api/workflows/executions/${id}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action })
        }).then(res => res.json());
      default:
        throw new Error(`Unknown action: ${action}`);
    }
  },
};

export const outputsApi = {
  getOutputs: (params?: {
    page?: number;
    limit?: number;
    executionId?: string;
    fileType?: string;
  }) =>
    outputsApiClass.getOutputs(params),
  getOutput: (id: string) => outputsApiClass.getOutput(id),
  deleteOutput: (id: string) => outputsApiClass.deleteOutput(id),
  downloadOutput: (id: string) => {
    return fetch(`/api/outputs/${id}/download`, {
      method: 'GET'
    }).then(res => res.json());
  },
};

// Re-export the files API as it's already being used
export const filesApi = {
  getFiles: (params?: {
    page?: number;
    limit?: number;
    filters?: FileFilters;
  }) => filesApiClass.getFiles(params),
  getFile: (id: string) => filesApiClass.getFile(id),
  getFileMetadata: (id: string) => filesApiClass.getFileMetadata(id),
  uploadFile: (file: File | Blob, onProgress?: (progress: number) => void) => filesApiClass.uploadFile(file, onProgress),
  deleteFile: (id: string) => filesApiClass.deleteFile(id),
};