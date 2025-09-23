# Project Configuration
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "us-central1-a"
}

# Storage Configuration
variable "raw_videos_bucket_name" {
  description = "Name for the raw videos bucket"
  type        = string
}

variable "processed_outputs_bucket_name" {
  description = "Name for the processed outputs bucket"
  type        = string
}

# Artifact Registry Configuration
variable "artifact_registry_repository" {
  description = "Artifact Registry repository name"
  type        = string
  default     = "super-over-alchemy"
}

# Service Configuration
variable "gemini_api_key" {
  description = "Gemini API key for scene analysis"
  type        = string
  sensitive   = true
}

variable "gemini_model" {
  description = "Gemini model to use"
  type        = string
  default     = "models/gemini-1.5-pro-latest"
}

variable "chunk_duration" {
  description = "Default video chunk duration in seconds"
  type        = number
  default     = 60
}

variable "compress_resolution" {
  description = "Default compression resolution"
  type        = string
  default     = ""
}

variable "workflow_name" {
  description = "Name of the Cloud Workflow"
  type        = string
  default     = "pipeline-orchestrator"
}