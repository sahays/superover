output "topic_name" {
  description = "Name of the created Pub/Sub topic"
  value       = google_pubsub_topic.topic.name
}

output "subscription_name" {
  description = "Name of the created Pub/Sub subscription"
  value       = google_pubsub_subscription.subscription.name
}

output "topic_id" {
  description = "Full resource ID of the topic"
  value       = google_pubsub_topic.topic.id
}