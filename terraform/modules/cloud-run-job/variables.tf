variable "job_name" {
  description = "Name of the Cloud Run job"
  type        = string
}

variable "location" {
  description = "GCP region for the Cloud Run job"
  type        = string
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "image_url" {
  description = "Container image URL from Artifact Registry"
  type        = string
}

variable "service_account_email" {
  description = "Service account to run the job as"
  type        = string
}

variable "pubsub_service_account_email" {
  description = "Pub/Sub service account that will invoke the job"
  type        = string
}

variable "environment_variables" {
  description = "Environment variables for the job"
  type        = map(string)
  default     = {}
}

variable "timeout_seconds" {
  description = "Job timeout in seconds"
  type        = number
  default     = 3600
}

variable "max_retries" {
  description = "Maximum number of retries for failed jobs"
  type        = number
  default     = 3
}

variable "memory_limit" {
  description = "Memory limit for the job"
  type        = string
  default     = "2Gi"
}

variable "cpu_limit" {
  description = "CPU limit for the job"
  type        = string
  default     = "2"
}
