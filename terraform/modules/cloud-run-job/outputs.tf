output "job_name" {
  description = "Name of the Cloud Run job"
  value       = google_cloud_run_v2_job.job.name
}

output "job_id" {
  description = "Full identifier of the Cloud Run job"
  value       = google_cloud_run_v2_job.job.id
}
