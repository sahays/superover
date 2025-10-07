resource "google_service_account" "pubsub_invoker" {
  account_id   = var.pubsub_invoker_name
  display_name = "Pub/Sub Cloud Run Invoker"
  description  = "Service account for Pub/Sub to invoke Cloud Run services"
}

resource "google_service_account" "services" {
  account_id   = var.services_sa_name
  display_name = "Super Over Services"
  description  = "Service account for Super Over Alchemy processing services"
}

# Grant services SA access to Cloud Storage
resource "google_project_iam_member" "services_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.services.email}"
}

# Grant services SA access to Firestore
resource "google_project_iam_member" "services_firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.services.email}"
}

# Grant services SA access to Cloud Logging
resource "google_project_iam_member" "services_logging_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.services.email}"
}

# Grant services SA access to Pub/Sub
resource "google_project_iam_member" "services_pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.services.email}"
}

resource "google_project_iam_member" "services_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.services.email}"
}