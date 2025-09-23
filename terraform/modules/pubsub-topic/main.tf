resource "google_pubsub_subscription" "subscription" {
  name  = var.subscription_name
  topic = var.topic_name

  push_config {
    push_endpoint = var.push_endpoint

    attributes = {
      x-goog-version = "v1"
    }

    oidc_token {
      service_account_email = var.service_account_email
    }
  }

  ack_deadline_seconds = 600
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

# Grant the service account permission to receive messages
resource "google_pubsub_subscription_iam_member" "subscriber" {
  subscription = google_pubsub_subscription.subscription.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${var.service_account_email}"
}

# Grant Cloud Run invoker permission
resource "google_cloud_run_service_iam_member" "invoker" {
  location = var.service_location
  project  = var.project_id
  service  = var.service_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.service_account_email}"
}