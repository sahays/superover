resource "google_cloud_run_v2_job" "job" {
  name     = var.job_name
  location = var.location
  project  = var.project_id

  template {
    template {
      service_account = var.service_account_email
      timeout         = "${var.timeout_seconds}s"
      max_retries     = var.max_retries

      containers {
        image = var.image_url

        resources {
          limits = {
            memory = var.memory_limit
            cpu    = var.cpu_limit
          }
        }

        dynamic "env" {
          for_each = var.environment_variables
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
    ]
  }
}

# IAM binding to allow Pub/Sub to invoke the job
resource "google_cloud_run_v2_job_iam_member" "pubsub_invoker" {
  project  = google_cloud_run_v2_job.job.project
  location = google_cloud_run_v2_job.job.location
  name     = google_cloud_run_v2_job.job.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.pubsub_service_account_email}"
}
