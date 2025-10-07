resource "google_cloud_run_service" "service" {
  name     = var.service_name
  location = var.location
  project  = var.project_id

  metadata {
    annotations = {
      "run.googleapis.com/ingress" = var.ingress
    }
  }

  template {
    metadata {
      annotations = {
        "autoscaling.knative.dev/maxScale" = tostring(var.max_instances)
        "autoscaling.knative.dev/minScale" = tostring(var.min_instances)
        "run.googleapis.com/execution-environment" = "gen2"
      }
    }

    spec {
      service_account_name = var.service_account_email
      timeout_seconds      = var.timeout_seconds

      containers {
        image = var.image_url

        resources {
          limits = {
            memory = var.memory_limit
            cpu    = var.cpu_limit
          }
        }

        dynamic "ports" {
          for_each = var.is_worker ? [] : [1]
          content {
            container_port = var.port
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

  traffic {
    percent         = 100
    latest_revision = true
  }

  lifecycle {
    ignore_changes = [
      template[0].metadata[0].annotations["run.googleapis.com/operation-id"],
    ]
  }
}

# Configure service access (public or private) using the more robust iam_binding resource
resource "google_cloud_run_service_iam_binding" "invoker" {
  location = google_cloud_run_service.service.location
  project  = google_cloud_run_service.service.project
  service  = google_cloud_run_service.service.name
  role     = "roles/run.invoker"
  members = var.allow_public_access ? [
    "allUsers",
  ] : [
    "serviceAccount:${var.service_account_email}",
  ]
}