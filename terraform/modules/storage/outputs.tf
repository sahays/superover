output "raw_videos_bucket_name" {
  description = "Name of the raw videos bucket"
  value       = google_storage_bucket.raw_videos.name
}

output "processed_outputs_bucket_name" {
  description = "Name of the processed outputs bucket"
  value       = google_storage_bucket.processed_outputs.name
}

output "raw_videos_bucket_url" {
  description = "URL of the raw videos bucket"
  value       = google_storage_bucket.raw_videos.url
}

output "processed_outputs_bucket_url" {
  description = "URL of the processed outputs bucket"
  value       = google_storage_bucket.processed_outputs.url
}