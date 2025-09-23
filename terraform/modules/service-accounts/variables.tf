variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "pubsub_invoker_name" {
  description = "Name for the Pub/Sub invoker service account"
  type        = string
  default     = "pubsub-invoker"
}

variable "services_sa_name" {
  description = "Name for the services service account"
  type        = string
  default     = "super-over-services"
}