resource "google_storage_bucket" "raw_videos" {
  name          = var.raw_videos_bucket_name
  location      = var.location
  project       = var.project_id
  force_destroy = true

  uniform_bucket_level_access = true

  versioning {
    enabled = false
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket" "processed_outputs" {
  name          = var.processed_outputs_bucket_name
  location      = var.location
  project       = var.project_id
  force_destroy = true

  uniform_bucket_level_access = true

  versioning {
    enabled = false
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type = "Delete"
    }
  }
}

# Pub/Sub notifications for raw videos bucket
resource "google_storage_notification" "raw_videos_notification" {
  for_each = {
    for key, config in var.pubsub_topics : key => config
    if config.path_filter == null || config.path_filter == ""
  }

  bucket         = google_storage_bucket.raw_videos.name
  payload_format = "JSON_API_V1"
  topic          = each.value.topic_name
  event_types    = ["OBJECT_FINALIZE"]

  depends_on = [google_pubsub_topic_iam_member.notification_publisher]
}

# Pub/Sub notifications for processed outputs bucket with path filters
resource "google_storage_notification" "processed_outputs_notification" {
  for_each = {
    for key, config in var.pubsub_topics : key => config
    if config.path_filter != null && config.path_filter != ""
  }

  bucket           = google_storage_bucket.processed_outputs.name
  payload_format   = "JSON_API_V1"
  topic            = each.value.topic_name
  event_types      = ["OBJECT_FINALIZE"]
  object_name_prefix = each.value.path_filter

  depends_on = [google_pubsub_topic_iam_member.notification_publisher]
}

# Grant GCS permission to publish to Pub/Sub topics
resource "google_pubsub_topic_iam_member" "notification_publisher" {
  for_each = var.pubsub_topics

  topic  = each.value.topic_name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.project.number}@gs-project-accounts.iam.gserviceaccount.com"
}

data "google_project" "project" {
  project_id = var.project_id
}