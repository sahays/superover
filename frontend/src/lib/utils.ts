import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 Bytes'

  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

export function formatDuration(seconds: number): string {
  if (!seconds || seconds < 0) return '0:00'

  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

export function truncateFilename(filename: string, maxLength: number = 30): string {
  if (!filename || filename.length <= maxLength) return filename

  const parts = filename.split('.')
  const ext = parts.length > 1 ? parts.pop() : ''
  const name = parts.join('.')
  
  if (!ext) {
    return name.substring(0, maxLength - 3) + '...'
  }

  const extLength = ext.length + 1 // +1 for dot
  const availableNameLength = maxLength - extLength - 3 // -3 for ...

  if (availableNameLength <= 0) {
    return filename.substring(0, maxLength - 3) + '...'
  }

  const start = name.substring(0, Math.ceil(availableNameLength / 2))
  const end = name.substring(name.length - Math.floor(availableNameLength / 2))

  return `${start}...${end}.${ext}`
}
