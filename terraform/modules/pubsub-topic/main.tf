resource "google_pubsub_topic" "topic" {
  name = var.topic_name
}

resource "google_pubsub_subscription" "subscription" {
  name  = var.subscription_name
  topic = google_pubsub_topic.topic.name

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
  location = data.google_cloud_run_service.service.location
  project  = var.project_id
  service  = data.google_cloud_run_service.service.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.service_account_email}"
}

data "google_cloud_run_service" "service" {
  name     = regex("services/([^/]+)$", var.push_endpoint)[0]
  location = regex("locations/([^/]+)/", var.push_endpoint)[0]
  project  = var.project_id
}