output "topic_name" {
  description = "Name of the Pub/Sub topic"
  value       = var.topic_name
}

output "subscription_name" {
  description = "Name of the created Pub/Sub subscription"
  value       = google_pubsub_subscription.subscription.name
}

output "subscription_id" {
  description = "Full resource ID of the subscription"
  value       = google_pubsub_subscription.subscription.id
}