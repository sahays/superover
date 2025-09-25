output "artifact_registry_repository_url" {
  description = "URL of the Artifact Registry repository"
  value       = google_artifact_registry_repository.repository.name
}

output "raw_videos_bucket_name" {
  description = "Name of the raw videos bucket"
  value       = module.storage.raw_videos_bucket_name
}

output "processed_outputs_bucket_name" {
  description = "Name of the processed outputs bucket"
  value       = module.storage.processed_outputs_bucket_name
}

output "service_urls" {
  description = "URLs of the deployed Cloud Run services"
  value = {
    video_processor  = module.video_processor_service.service_url
    audio_extractor  = module.audio_extractor_service.service_url
    scene_analyzer   = module.scene_analyzer_service.service_url
    media_inspector  = module.media_inspector_service.service_url
    workflow_manager = module.workflow_manager_service.service_url
    job_creator      = module.job_creator_service.service_url
  }
}

output "pubsub_topics" {
  description = "Names of the created Pub/Sub topics"
  value = {
    video_processor_jobs = google_pubsub_topic.video_processor_jobs.name
    audio_extractor_jobs = google_pubsub_topic.audio_extractor_jobs.name
    scene_analyzer_jobs  = google_pubsub_topic.scene_analyzer_jobs.name
    media_inspector_jobs = google_pubsub_topic.media_inspector_jobs.name
  }
}

output "service_account_emails" {
  description = "Email addresses of the created service accounts"
  value = {
    pubsub_invoker = module.service_accounts.pubsub_invoker_email
    services       = module.service_accounts.services_sa_email
  }
}