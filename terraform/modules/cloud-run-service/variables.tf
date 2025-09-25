variable "service_name" {
  description = "Name of the Cloud Run service"
  type        = string
}

variable "location" {
  description = "GCP region for the Cloud Run service"
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
  description = "Service account to run the service as"
  type        = string
}

variable "environment_variables" {
  description = "Environment variables for the service"
  type        = map(string)
  default     = {}
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 10
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 1
}

variable "timeout_seconds" {
  description = "Request timeout in seconds"
  type        = number
  default     = 3600
}

variable "memory_limit" {
  description = "Memory limit for the service"
  type        = string
  default     = "2Gi"
}

variable "cpu_limit" {
  description = "CPU limit for the service"
  type        = string
  default     = "2"
}