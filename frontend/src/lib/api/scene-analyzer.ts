import { apiClient } from './client';

export interface SceneAnalysisJob {
  job_id: string;
  gcs_path: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  created_at: string;
  worker_start_time?: string;
  worker_end_time?: string;
  media_info?: {
    duration: number;
    width: number;
    height: number;
    codec: string;
  };
  results_path?: string;
  error?: string;
}

export interface SignedUrlResponse {
  signed_url: string;
  gcs_path: string;
}

export interface CreateJobRequest {
  gcs_path: string;
}

export interface CreateJobResponse {
  job_id: string;
  status: string;
}

class SceneAnalyzerApi {
  private baseUrl: string;

  constructor() {
    // Use the API service URL from environment or default to /api
    this.baseUrl = process.env.NEXT_PUBLIC_API_URL || '/api';
  }

  /**
   * Request a signed URL for uploading a video file to GCS
   */
  async getSignedUploadUrl(fileName: string, contentType: string): Promise<SignedUrlResponse> {
    return apiClient.post<SignedUrlResponse>(`${this.baseUrl}/v1/uploads/signed-url`, {
      file_name: fileName,
      content_type: contentType,
    });
  }

  /**
   * Upload a file directly to GCS using a signed URL
   */
  async uploadToGcs(
    signedUrl: string,
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<void> {
    const xhr = new XMLHttpRequest();

    return new Promise((resolve, reject) => {
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable && onProgress) {
          const progress = (e.loaded / e.total) * 100;
          onProgress(progress);
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve();
        } else {
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      });

      xhr.addEventListener('error', () => {
        reject(new Error('Upload failed'));
      });

      xhr.open('PUT', signedUrl);
      xhr.setRequestHeader('Content-Type', file.type);
      xhr.send(file);
    });
  }

  /**
   * Create a new scene analysis job
   */
  async createJob(gcsPath: string): Promise<CreateJobResponse> {
    return apiClient.post<CreateJobResponse>(`${this.baseUrl}/v1/scene-analysis/jobs`, {
      gcs_path: gcsPath,
    });
  }

  /**
   * Get the status of a scene analysis job
   */
  async getJobStatus(jobId: string): Promise<SceneAnalysisJob> {
    return apiClient.get<SceneAnalysisJob>(`${this.baseUrl}/v1/scene-analysis/jobs/${jobId}`);
  }

  /**
   * Upload a file and create a scene analysis job (convenience method)
   */
  async uploadAndCreateJob(
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<{ jobId: string; gcsPath: string }> {
    // Step 1: Get signed URL
    const { signed_url, gcs_path } = await this.getSignedUploadUrl(file.name, file.type);

    // Step 2: Upload file to GCS
    await this.uploadToGcs(signed_url, file, onProgress);

    // Step 3: Create analysis job
    const { job_id } = await this.createJob(gcs_path);

    return { jobId: job_id, gcsPath: gcs_path };
  }

  /**
   * Poll job status until completion or failure
   */
  async pollJobStatus(
    jobId: string,
    onStatusChange?: (job: SceneAnalysisJob) => void,
    pollInterval: number = 5000
  ): Promise<SceneAnalysisJob> {
    return new Promise((resolve, reject) => {
      const poll = async () => {
        try {
          const job = await this.getJobStatus(jobId);

          if (onStatusChange) {
            onStatusChange(job);
          }

          if (job.status === 'completed') {
            resolve(job);
          } else if (job.status === 'failed') {
            reject(new Error(job.error || 'Job failed'));
          } else {
            // Continue polling
            setTimeout(poll, pollInterval);
          }
        } catch (error) {
          reject(error);
        }
      };

      poll();
    });
  }
}

export const sceneAnalyzerApi = new SceneAnalyzerApi();
