output "pubsub_invoker_email" {
  description = "Email of the Pub/Sub invoker service account"
  value       = google_service_account.pubsub_invoker.email
}

output "services_sa_email" {
  description = "Email of the services service account"
  value       = google_service_account.services.email
}

output "pubsub_invoker_id" {
  description = "ID of the Pub/Sub invoker service account"
  value       = google_service_account.pubsub_invoker.id
}

output "services_sa_id" {
  description = "ID of the services service account"
  value       = google_service_account.services.id
}