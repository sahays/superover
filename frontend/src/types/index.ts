// Core data models matching the backend services

export type FileStatus = 'uploading' | 'uploaded' | 'processing' | 'failed';
export type JobStatus = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
export type ExecutionStatus = JobStatus;

// File Management Types
export interface FileItem {
  id: string;
  name: string;
  size: number;
  type: string;
  gcsPath: string;
  uploadedAt: string;
  metadata?: FileMetadata;
  status: FileStatus;
  thumbnailUrl?: string;
  previewUrl?: string;
}

export interface FileMetadata {
  duration?: number;
  width?: number;
  height?: number;
  fps?: number;
  bitrate?: number;
  codec?: string;
  format?: string;
  channels?: number;
  sampleRate?: number;
  fileSize: number;
  createdAt: string;
}

export interface FileUploadProgress {
  fileId: string;
  fileName: string;
  progress: number;
  status: 'uploading' | 'processing' | 'completed' | 'failed';
  error?: string;
}

// Pipeline and Workflow Types
export interface PipelineStep {
  order: number;
  serviceName: string;
  topic: string;
  parameters?: Record<string, unknown>;
}

export interface Pipeline {
  id: string;
  name: string;
  description: string;
  steps: PipelineStep[];
  defaultParameters: Record<string, unknown>;
  estimatedDuration?: number;
  category: 'video' | 'audio' | 'analysis' | 'full';
  status: 'active' | 'draft' | 'inactive';
  createdAt: string;
  updatedAt: string;
}

export interface WorkflowParameters {
  // Video processing parameters
  resolution?: '480p' | '720p' | '1080p' | '4k';
  chunkDuration?: number;
  videoCodec?: 'h264' | 'h265' | 'vp9';
  videoBitrate?: number;

  // Audio processing parameters
  audioCodec?: 'aac' | 'flac' | 'mp3';
  audioBitrate?: number;
  sampleRate?: number;
  channels?: number;

  // Analysis parameters
  analysisDepth?: 'basic' | 'detailed' | 'comprehensive';
  sceneDetection?: boolean;
  objectDetection?: boolean;
  speechRecognition?: boolean;
  emotionAnalysis?: boolean;

  // Custom parameters
  customParameters?: Record<string, unknown>;
}

// Job and Execution Types
export interface Job {
  id: string;
  pipelineId: string;
  sourceFile: string;
  status: JobStatus;
  createdAt: string;
  updatedAt: string;
  retryCount: number;
  checkpoints: Record<string, JobStatus>;
  progress: Record<string, { completed: number; total: number }>;
  outputs: Record<string, string>;
  error?: string;
  parameters: WorkflowParameters;
}

export interface WorkflowExecution {
  id: string;
  jobId: string;
  pipelineId: string;
  pipelineName: string;
  sourceFileName: string;
  parameters: WorkflowParameters;
  status: ExecutionStatus;
  startedAt: string;
  completedAt?: string;
  duration?: number;
  progress: {
    currentStep: string;
    completed: number;
    total: number;
    percentage: number;
  };
  results: ExecutionResult[];
  logs: ExecutionLog[];
  error?: string;
}

export interface ExecutionResult {
  stepName: string;
  serviceName: string;
  status: 'completed' | 'failed' | 'skipped';
  outputPaths: string[];
  metadata?: Record<string, unknown>;
  duration: number;
  error?: string;
}

export interface ExecutionLog {
  id: string;
  executionId: string;
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'debug';
  message: string;
  stepName?: string;
  serviceName?: string;
  metadata?: Record<string, unknown>;
}

// Output Types
export interface OutputFile {
  id: string;
  executionId: string;
  stepName: string;
  fileName: string;
  filePath: string;
  fileType: string;
  size: number;
  createdAt: string;
  downloadUrl?: string;
  previewUrl?: string;
  metadata?: Record<string, unknown>;
}

export interface AnalysisResult {
  id: string;
  executionId: string;
  stepName: string;
  analysisType: 'scene' | 'audio' | 'metadata' | 'transcript';
  results: Record<string, unknown>;
  confidence?: number;
  createdAt: string;
}

// API Response Types
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface PaginatedResponse<T> {
  success: boolean;
  data: T[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
    hasNext: boolean;
    hasPrev: boolean;
  };
}

// Filter and Search Types
export interface FileFilters {
  type?: string[];
  status?: FileStatus[];
  uploadedAfter?: string;
  uploadedBefore?: string;
  sizeMin?: number;
  sizeMax?: number;
  search?: string;
}

export interface ExecutionFilters {
  status?: ExecutionStatus[];
  pipelineId?: string[];
  startedAfter?: string;
  startedBefore?: string;
  search?: string;
}

// UI State Types
export interface AppState {
  user: User | null;
  theme: 'light' | 'dark';
  notifications: Notification[];
}

export interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  role: 'admin' | 'user';
  preferences: UserPreferences;
}

export interface UserPreferences {
  theme: 'light' | 'dark' | 'system';
  notifications: boolean;
  autoRefresh: boolean;
  defaultPipeline?: string;
}

export interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
  actionUrl?: string;
}

// Form Types
export interface FileUploadForm {
  files: FileList;
  pipelineId?: string;
  parameters?: WorkflowParameters;
}

export interface WorkflowCreateForm {
  name: string;
  description: string;
  pipelineId: string;
  parameters: WorkflowParameters;
  sourceFileId: string;
}

// Utility Types
export type LoadingState = 'idle' | 'loading' | 'success' | 'error';

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

// Real-time Update Types
export interface RealTimeUpdate {
  type: 'execution_update' | 'file_update' | 'notification';
  payload: unknown;
  timestamp: string;
}

// Error Types
export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ValidationError {
  field: string;
  message: string;
}