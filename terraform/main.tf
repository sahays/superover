terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",
    "pubsub.googleapis.com",
    "storage.googleapis.com",
    "firestore.googleapis.com",
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "workflows.googleapis.com",
    "eventarc.googleapis.com"
  ])

  service = each.value
  project = var.project_id

  disable_dependent_services = true
}

# Create Artifact Registry repository
resource "google_artifact_registry_repository" "repository" {
  location      = var.region
  repository_id = var.artifact_registry_repository
  description   = "Super Over Alchemy container images"
  format        = "DOCKER"

  depends_on = [google_project_service.required_apis]
}

# Create service accounts
module "service_accounts" {
  source = "./modules/service-accounts"

  project_id = var.project_id
}

# Create storage buckets
module "storage" {
  source = "./modules/storage"

  project_id                      = var.project_id
  location                        = var.region
  raw_videos_bucket_name          = var.raw_videos_bucket_name
  processed_outputs_bucket_name   = var.processed_outputs_bucket_name

  pubsub_topics = {
    raw_uploads = {
      topic_name  = google_pubsub_topic.video_processor_jobs.name
      path_filter = null
    }
    scene_analysis_trigger = {
      topic_name  = google_pubsub_topic.scene_analyzer_jobs.name
      path_filter = "_report.json"
    }
  }

  depends_on = [google_project_service.required_apis]
}

# Create Pub/Sub topics first (needed for storage notifications)
resource "google_pubsub_topic" "video_processor_jobs" {
  name = "video-processor-jobs"
}

resource "google_pubsub_topic" "audio_extractor_jobs" {
  name = "audio-extractor-jobs"
}

resource "google_pubsub_topic" "scene_analyzer_jobs" {
  name = "scene-analyzer-jobs"
}

resource "google_pubsub_topic" "media_inspector_jobs" {
  name = "media-inspector-jobs"
}

# Deploy Cloud Run services
module "video_processor_service" {
  source = "./modules/cloud-run-service"

  service_name          = "video-processor-service"
  location              = var.region
  project_id            = var.project_id
  image_url             = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repository}/video-processor:latest"
  service_account_email = module.service_accounts.services_sa_email

  environment_variables = {
    CHUNK_DURATION       = tostring(var.chunk_duration)
    COMPRESS_RESOLUTION  = var.compress_resolution
    COMPRESS_FIRST       = "false"
  }

  depends_on = [google_artifact_registry_repository.repository]
}

module "audio_extractor_service" {
  source = "./modules/cloud-run-service"

  service_name          = "audio-extractor-service"
  location              = var.region
  project_id            = var.project_id
  image_url             = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repository}/audio-extractor:latest"
  service_account_email = module.service_accounts.services_sa_email

  depends_on = [google_artifact_registry_repository.repository]
}

module "scene_analyzer_service" {
  source = "./modules/cloud-run-service"

  service_name          = "scene-analyzer-service"
  location              = var.region
  project_id            = var.project_id
  image_url             = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repository}/scene-analyzer:latest"
  service_account_email = module.service_accounts.services_sa_email

  environment_variables = {
    GEMINI_API_KEY = var.gemini_api_key
    GEMINI_MODEL   = var.gemini_model
  }

  depends_on = [google_artifact_registry_repository.repository]
}

module "media_inspector_service" {
  source = "./modules/cloud-run-service"

  service_name          = "media-inspector-service"
  location              = var.region
  project_id            = var.project_id
  image_url             = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repository}/media-inspector:latest"
  service_account_email = module.service_accounts.services_sa_email

  depends_on = [google_artifact_registry_repository.repository]
}

module "workflow_manager_service" {
  source = "./modules/cloud-run-service"

  service_name          = "workflow-manager-service"
  location              = var.region
  project_id            = var.project_id
  image_url             = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repository}/workflow-manager:latest"
  service_account_email = module.service_accounts.services_sa_email

  depends_on = [google_artifact_registry_repository.repository]
}

module "job_creator_service" {
  source = "./modules/cloud-run-service"

  service_name          = "job-creator-service"
  location              = var.region
  project_id            = var.project_id
  image_url             = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repository}/job-creator:latest"
  service_account_email = module.service_accounts.services_sa_email

  environment_variables = {
    GCP_PROJECT    = var.project_id
    GCP_LOCATION   = var.region
    WORKFLOW_NAME  = var.workflow_name
  }

  depends_on = [google_artifact_registry_repository.repository]
}

# Create Pub/Sub subscriptions
module "video_processor_pubsub" {
  source = "./modules/pubsub-topic"

  topic_name            = google_pubsub_topic.video_processor_jobs.name
  subscription_name     = "video-processor-sub"
  service_account_email = module.service_accounts.pubsub_invoker_email
  push_endpoint         = module.video_processor_service.service_url
  service_name          = "video-processor-service"
  service_location      = var.region
  project_id            = var.project_id
}

module "audio_extractor_pubsub" {
  source = "./modules/pubsub-topic"

  topic_name            = google_pubsub_topic.audio_extractor_jobs.name
  subscription_name     = "audio-extractor-sub"
  service_account_email = module.service_accounts.pubsub_invoker_email
  push_endpoint         = module.audio_extractor_service.service_url
  service_name          = "audio-extractor-service"
  service_location      = var.region
  project_id            = var.project_id
}

module "scene_analyzer_pubsub" {
  source = "./modules/pubsub-topic"

  topic_name            = google_pubsub_topic.scene_analyzer_jobs.name
  subscription_name     = "scene-analyzer-sub"
  service_account_email = module.service_accounts.pubsub_invoker_email
  push_endpoint         = module.scene_analyzer_service.service_url
  service_name          = "scene-analyzer-service"
  service_location      = var.region
  project_id            = var.project_id
}

module "media_inspector_pubsub" {
  source = "./modules/pubsub-topic"

  topic_name            = google_pubsub_topic.media_inspector_jobs.name
  subscription_name     = "media-inspector-sub"
  service_account_email = module.service_accounts.pubsub_invoker_email
  push_endpoint         = module.media_inspector_service.service_url
  service_name          = "media-inspector-service"
  service_location      = var.region
  project_id            = var.project_id
}

# Create Firestore database (import existing if present)
resource "google_firestore_database" "database" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.required_apis]

  lifecycle {
    # Prevent destruction of database with data
    prevent_destroy = false
  }
}

# Grant Cloud Build service account necessary permissions
resource "google_project_iam_member" "cloudbuild_logs_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
}

resource "google_project_iam_member" "cloudbuild_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
}

resource "google_project_iam_member" "cloudbuild_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
}

# Grant the default Compute Engine service account permissions to submit builds
# This is often needed when running gcloud builds submit from a GCE VM or Cloud Shell
resource "google_project_iam_member" "compute_sa_cloudbuild_editor" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.editor"
  member  = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

resource "google_project_iam_member" "compute_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

resource "google_project_iam_member" "compute_sa_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

resource "google_project_iam_member" "compute_sa_logs_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

data "google_project" "project" {
  project_id = var.project_id
}