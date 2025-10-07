terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  backend "local" {
    path = "terraform.tfstate"
  }
}

locals {
  env_vars = { for tuple in regexall("(.+?)=(.+)", file("../.env")) : tuple[0] => replace(tuple[1], "\"", "") }
}

provider "google" {
  project = local.env_vars.GCP_PROJECT_ID
  region  = local.env_vars.GCP_REGION
}

# --- Foundational Resources ---
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com", "pubsub.googleapis.com", "storage.googleapis.com",
    "firestore.googleapis.com", "cloudbuild.googleapis.com", "artifactregistry.googleapis.com",
    "logging.googleapis.com", "compute.googleapis.com"
  ])
  service                    = each.value
  project                    = local.env_vars.GCP_PROJECT_ID
  disable_dependent_services = true
}

resource "google_artifact_registry_repository" "repository" {
  location      = local.env_vars.GCP_REGION
  repository_id = "super-over-alchemy"
  description   = "Super Over Alchemy container images"
  format        = "DOCKER"
  depends_on    = [google_project_service.required_apis]
}

module "service_accounts" {
  source     = "./modules/service-accounts"
  project_id = local.env_vars.GCP_PROJECT_ID
}

# --- Cloud Run Services ---
module "frontend_service" {
  source                = "./modules/cloud-run-service"
  service_name          = "frontend-service"
  location              = local.env_vars.GCP_REGION
  project_id            = local.env_vars.GCP_PROJECT_ID
  image_url             = "${local.env_vars.GCP_REGION}-docker.pkg.dev/${local.env_vars.GCP_PROJECT_ID}/super-over-alchemy/frontend:latest"
  service_account_email = module.service_accounts.services_sa_email
  allow_public_access   = false
  min_instances         = 1
  port                  = 3000
  ingress               = "all"
  depends_on            = [google_artifact_registry_repository.repository]
}

module "api_service" {
  source                = "./modules/cloud-run-service"
  service_name          = "api-service"
  location              = local.env_vars.GCP_REGION
  project_id            = local.env_vars.GCP_PROJECT_ID
  image_url             = "${local.env_vars.GCP_REGION}-docker.pkg.dev/${local.env_vars.GCP_PROJECT_ID}/super-over-alchemy/api-service:latest"
  service_account_email = module.service_accounts.services_sa_email
  allow_public_access   = false
  min_instances         = 1
  ingress               = "all"
  environment_variables = {
    GCP_PROJECT_ID          = local.env_vars.GCP_PROJECT_ID
    RAW_UPLOADS_BUCKET_NAME = local.env_vars.RAW_UPLOADS_BUCKET_NAME
    JOBS_TOPIC_ID           = google_pubsub_topic.scene_analysis_jobs.name
    FRONTEND_URL            = "https://frontend-service-p2irpfu5ya-el.a.run.app"
  }
  depends_on = [google_pubsub_topic.scene_analysis_jobs]
}

module "scene_analyzer_worker" {
  source                        = "./modules/cloud-run-job"
  job_name                      = "scene-analyzer-worker"
  location                      = local.env_vars.GCP_REGION
  project_id                    = local.env_vars.GCP_PROJECT_ID
  image_url                     = "${local.env_vars.GCP_REGION}-docker.pkg.dev/${local.env_vars.GCP_PROJECT_ID}/super-over-alchemy/scene-analyzer-worker:latest"
  service_account_email         = module.service_accounts.services_sa_email
  pubsub_service_account_email  = module.service_accounts.pubsub_invoker_email
  cpu_limit                     = "2"
  memory_limit                  = "4Gi"
  timeout_seconds               = 3600 # 1 hour
  max_retries                   = 3
  environment_variables = {
    GCP_PROJECT_ID                = local.env_vars.GCP_PROJECT_ID
    PROCESSED_OUTPUTS_BUCKET_NAME = local.env_vars.PROCESSED_OUTPUTS_BUCKET_NAME
  }
  depends_on = [google_artifact_registry_repository.repository]
}

# --- Load Balancer ---
resource "google_compute_global_address" "frontend_ip" {
  name = "frontend-lb-ip"
}

resource "google_compute_region_network_endpoint_group" "frontend_neg" {
  name                  = "frontend-serverless-neg"
  network_endpoint_type = "SERVERLESS"
  region                = local.env_vars.GCP_REGION
  cloud_run {
    service = module.frontend_service.service_name
  }
}

resource "google_compute_region_network_endpoint_group" "api_neg" {
  name                  = "api-serverless-neg"
  network_endpoint_type = "SERVERLESS"
  region                = local.env_vars.GCP_REGION
  cloud_run {
    service = module.api_service.service_name
  }
}

resource "google_compute_backend_service" "frontend_backend" {
  name                  = "frontend-backend-service"
  protocol              = "HTTP"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  backend {
    group = google_compute_region_network_endpoint_group.frontend_neg.id
  }
}

resource "google_compute_backend_service" "api_backend" {
  name                  = "api-backend-service"
  protocol              = "HTTP"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  backend {
    group = google_compute_region_network_endpoint_group.api_neg.id
  }
}

resource "google_compute_url_map" "frontend_url_map" {
  name            = "frontend-lb-url-map"
  default_service = google_compute_backend_service.frontend_backend.id

  path_matcher {
    name            = "api-paths"
    default_service = google_compute_backend_service.frontend_backend.id
    path_rule {
      paths   = ["/api/*"]
      service = google_compute_backend_service.api_backend.id
    }
  }
}

resource "google_compute_managed_ssl_certificate" "frontend_ssl" {
  name = "frontend-ssl-cert"
  managed {
    domains = ["${replace(google_compute_global_address.frontend_ip.address, ".", "-")}.sslip.io"]
  }
}

resource "google_compute_target_https_proxy" "frontend_proxy" {
  name             = "frontend-https-proxy"
  url_map          = google_compute_url_map.frontend_url_map.id
  ssl_certificates = [google_compute_managed_ssl_certificate.frontend_ssl.id]
}

resource "google_compute_global_forwarding_rule" "frontend_forwarding_rule" {
  name                  = "frontend-forwarding-rule"
  target                = google_compute_target_https_proxy.frontend_proxy.id
  ip_address            = google_compute_global_address.frontend_ip.address
  port_range            = "443"
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# --- Pub/Sub for Task Queue ---
resource "google_pubsub_topic" "scene_analysis_jobs" {
  name = "scene-analysis-jobs"
}

resource "google_pubsub_subscription" "scene_analysis_jobs_push_sub" {
  name  = "scene-analysis-jobs-push-sub"
  topic = google_pubsub_topic.scene_analysis_jobs.name

  ack_deadline_seconds = 600

  push_config {
    push_endpoint = "https://${local.env_vars.GCP_REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${local.env_vars.GCP_PROJECT_ID}/jobs/${module.scene_analyzer_worker.job_name}:run"

    oidc_token {
      service_account_email = module.service_accounts.pubsub_invoker_email
    }

    attributes = {
      x-goog-version = "v1"
    }
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  depends_on = [module.scene_analyzer_worker]
}

# --- Other Resources (Storage, Firestore, IAM) ---
module "storage" {
  source                        = "./modules/storage"
  project_id                    = local.env_vars.GCP_PROJECT_ID
  location                      = local.env_vars.GCP_REGION
  raw_videos_bucket_name        = local.env_vars.RAW_UPLOADS_BUCKET_NAME
  processed_outputs_bucket_name = local.env_vars.PROCESSED_OUTPUTS_BUCKET_NAME
  pubsub_topics = {
    raw_uploads = {
      topic_name  = google_pubsub_topic.scene_analysis_jobs.name
      path_filter = null
    }
  }
}

resource "google_firestore_database" "database" {
  project     = local.env_vars.GCP_PROJECT_ID
  name        = "(default)"
  location_id = local.env_vars.GCP_REGION
  type        = "FIRESTORE_NATIVE"
}

data "google_project" "project" {
  project_id = local.env_vars.GCP_PROJECT_ID
}

locals {
  cloud_build_sa = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
  compute_sa     = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

resource "google_project_iam_binding" "cloudbuild_bindings" {
  project = data.google_project.project.project_id
  role    = "roles/cloudbuild.builds.editor"
  members = [local.compute_sa]
}

resource "google_project_iam_binding" "run_admin_bindings" {
  project = data.google_project.project.project_id
  role    = "roles/run.admin"
  members = [local.cloud_build_sa]
}

resource "google_project_iam_binding" "iam_sa_user_bindings" {
  project = data.google_project.project.project_id
  role    = "roles/iam.serviceAccountUser"
  members = [local.cloud_build_sa]
}

resource "google_project_iam_binding" "logging_writer_bindings" {
  project = data.google_project.project.project_id
  role    = "roles/logging.logWriter"
  members = [
    local.cloud_build_sa,
    local.compute_sa,
  ]
}

resource "google_project_iam_binding" "storage_admin_bindings" {
  project = data.google_project.project.project_id
  role    = "roles/storage.admin"
  members = [
    local.cloud_build_sa,
    local.compute_sa,
  ]
}

resource "google_project_iam_binding" "ar_writer_bindings" {
  project = data.google_project.project.project_id
  role    = "roles/artifactregistry.writer"
  members = [
    local.cloud_build_sa,
    local.compute_sa,
  ]
}


# Temporary HTTP forwarding rule for testing while SSL provisions
resource "google_compute_target_http_proxy" "frontend_http_proxy" {
  name    = "frontend-http-proxy"
  url_map = google_compute_url_map.frontend_url_map.id
}

resource "google_compute_global_forwarding_rule" "frontend_http_forwarding_rule" {
  name                  = "frontend-http-forwarding-rule"
  target                = google_compute_target_http_proxy.frontend_http_proxy.id
  ip_address            = google_compute_global_address.frontend_ip.address
  port_range            = "80"
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
