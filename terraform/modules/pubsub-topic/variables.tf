variable "topic_name" {
  description = "Name of the Pub/Sub topic"
  type        = string
}

variable "subscription_name" {
  description = "Name of the Pub/Sub subscription"
  type        = string
}

variable "service_account_email" {
  description = "Service account email for push authentication"
  type        = string
}

variable "push_endpoint" {
  description = "Cloud Run service URL for push subscription"
  type        = string
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
}