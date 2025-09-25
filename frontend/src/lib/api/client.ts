import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosProgressEvent } from 'axios';

class ApiClient {
  private axios: AxiosInstance;

  constructor(baseURL: string = '/api') {
    this.axios = axios.create({
      baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor
    this.axios.interceptors.request.use(
      (config) => {
        // Add auth token if available
        const token = this.getAuthToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor
    this.axios.interceptors.response.use(
      (response) => response,
      (error) => {
        // Handle common errors
        if (error.response?.status === 401) {
          // Handle unauthorized access
          this.handleUnauthorized();
        }

        // Transform error to a consistent format
        const apiError = {
          message: error.response?.data?.message || error.message || 'An error occurred',
          status: error.response?.status,
          code: error.response?.data?.code || error.code,
        };

        return Promise.reject(apiError);
      }
    );
  }

  private getAuthToken(): string | null {
    // In a real app, get from localStorage, cookies, etc.
    return null;
  }

  private handleUnauthorized() {
    // Handle logout, redirect to login, etc.
    console.warn('Unauthorized access detected');
  }

  // Generic request methods
  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response: AxiosResponse<T> = await this.axios.get(url, config);
    return response.data;
  }

  async post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    const response: AxiosResponse<T> = await this.axios.post(url, data, config);
    return response.data;
  }

  async put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    const response: AxiosResponse<T> = await this.axios.put(url, data, config);
    return response.data;
  }

  async patch<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    const response: AxiosResponse<T> = await this.axios.patch(url, data, config);
    return response.data;
  }

  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response: AxiosResponse<T> = await this.axios.delete(url, config);
    return response.data;
  }

  // File upload with progress tracking
  async uploadFile<T>(
    url: string,
    formData: FormData,
    onProgress?: (progressEvent: AxiosProgressEvent) => void
  ): Promise<T> {
    const response: AxiosResponse<T> = await this.axios.post(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: onProgress,
    });
    return response.data;
  }

  // Download file
  async downloadFile(url: string, filename?: string): Promise<void> {
    const response = await this.axios.get(url, {
      responseType: 'blob',
    });

    // Create blob URL and trigger download
    const blob = new Blob([response.data]);
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = filename || 'download';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
  }
}

// Create and export a singleton instance
export const apiClient = new ApiClient();
export { ApiClient };