variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "location" {
  description = "GCS bucket location"
  type        = string
  default     = "US"
}

variable "raw_videos_bucket_name" {
  description = "Name for the raw videos bucket"
  type        = string
}

variable "processed_outputs_bucket_name" {
  description = "Name for the processed outputs bucket"
  type        = string
}

variable "pubsub_topics" {
  description = "Map of trigger patterns to Pub/Sub topic names"
  type = map(object({
    topic_name = string
    path_filter = optional(string)
  }))
}