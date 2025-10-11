/**
 * Scene Analysis Export Utilities
 * Handles JSON and CSV export of scene analysis results with timestamp adjustments
 */

export interface SceneResult {
  result_id: string
  result_type: string
  result_data: any
}

export interface SceneJob {
  job_id: string
  video_id: string
  config: {
    chunk_duration: number
    compressed_video_path?: string
  }
  status: string
  results?: any
}

/**
 * Adjusts timestamps in scene analysis results to be sequential across chunks
 */
export function adjustTimestampsForSequentialVideo(results: SceneResult[], chunkDuration: number): SceneResult[] {
  return results.map((result, chunkIndex) => {
    const chunkStartTime = chunkIndex * chunkDuration
    const adjustedResult = { ...result }

    // Deep copy result_data and adjust timestamps
    if (result.result_data) {
      adjustedResult.result_data = JSON.parse(JSON.stringify(result.result_data))

      // Add chunk metadata
      adjustedResult.result_data.chunk_metadata = {
        chunk_index: chunkIndex,
        chunk_start_time: chunkStartTime,
        chunk_duration: chunkDuration,
        video_timestamp_start: chunkStartTime,
        video_timestamp_end: chunkStartTime + chunkDuration,
      }

      // Adjust timestamps in scenes if they exist
      if (adjustedResult.result_data.scenes && Array.isArray(adjustedResult.result_data.scenes)) {
        adjustedResult.result_data.scenes = adjustedResult.result_data.scenes.map((scene: any) => {
          const adjustedScene = { ...scene }

          // Adjust timestamp field if it exists (in seconds)
          if (typeof adjustedScene.timestamp === 'number') {
            adjustedScene.video_timestamp = chunkStartTime + adjustedScene.timestamp
            adjustedScene.chunk_timestamp = adjustedScene.timestamp
          }

          // Adjust start_time/end_time if they exist
          if (typeof adjustedScene.start_time === 'number') {
            adjustedScene.video_start_time = chunkStartTime + adjustedScene.start_time
            adjustedScene.chunk_start_time = adjustedScene.start_time
          }
          if (typeof adjustedScene.end_time === 'number') {
            adjustedScene.video_end_time = chunkStartTime + adjustedScene.end_time
            adjustedScene.chunk_end_time = adjustedScene.end_time
          }

          return adjustedScene
        })
      }

      // Adjust timestamps in any other time-based arrays (events, moments, etc.)
      ;['events', 'moments', 'highlights'].forEach((key) => {
        if (adjustedResult.result_data[key] && Array.isArray(adjustedResult.result_data[key])) {
          adjustedResult.result_data[key] = adjustedResult.result_data[key].map((item: any) => {
            const adjustedItem = { ...item }
            if (typeof adjustedItem.timestamp === 'number') {
              adjustedItem.video_timestamp = chunkStartTime + adjustedItem.timestamp
              adjustedItem.chunk_timestamp = adjustedItem.timestamp
            }
            if (typeof adjustedItem.start_time === 'number') {
              adjustedItem.video_start_time = chunkStartTime + adjustedItem.start_time
              adjustedItem.chunk_start_time = adjustedItem.start_time
            }
            if (typeof adjustedItem.end_time === 'number') {
              adjustedItem.video_end_time = chunkStartTime + adjustedItem.end_time
              adjustedItem.chunk_end_time = adjustedItem.end_time
            }
            return adjustedItem
          })
        }
      })
    }

    return adjustedResult
  })
}

/**
 * Flattens nested objects into dot notation keys for CSV export
 */
function flattenObject(obj: any, prefix = '', depth = 0, maxDepth = 10): Record<string, any> {
  const flattened: Record<string, any> = {}

  // Prevent infinite recursion
  if (depth > maxDepth) {
    return { [prefix || 'data']: JSON.stringify(obj) }
  }

  // Handle non-object types
  if (obj === null || obj === undefined) {
    return { [prefix || 'value']: '' }
  }

  if (typeof obj !== 'object') {
    return { [prefix || 'value']: String(obj) }
  }

  for (const key in obj) {
    if (!obj.hasOwnProperty(key)) continue

    const fullKey = prefix ? `${prefix}.${key}` : key
    const value = obj[key]

    // Skip these fields
    if (key === 'gemini_file_uri' || key === 'chunk_metadata' || key === 'blocked' ||
        key.includes('chunk_') || key.includes('video_')) {
      continue
    }

    try {
      if (value === null || value === undefined) {
        flattened[fullKey] = ''
      } else if (Array.isArray(value)) {
        if (value.length === 0) {
          flattened[fullKey] = ''
        } else if (value.length > 50) {
          // Prevent explosion for very large arrays
          flattened[fullKey] = `[${value.length} items]`
          flattened[`${fullKey}_sample`] = value.slice(0, 3).map(v =>
            typeof v === 'object' ? JSON.stringify(v) : String(v)
          ).join('; ')
        } else if (typeof value[0] === 'object' && value[0] !== null) {
          // Array of objects - check if they're all similar structure
          const firstKeys = Object.keys(value[0])
          const allSimilar = value.every(item =>
            typeof item === 'object' && item !== null &&
            Object.keys(item).every(k => firstKeys.includes(k))
          )

          if (allSimilar && value.length <= 10) {
            // Flatten each with index
            value.forEach((item, idx) => {
              const itemFlattened = flattenObject(item, `${fullKey}[${idx}]`, depth + 1, maxDepth)
              Object.assign(flattened, itemFlattened)
            })
          } else {
            // Too many or inconsistent - summarize
            flattened[fullKey] = value.map(v =>
              typeof v === 'object' ? JSON.stringify(v) : String(v)
            ).join(' | ')
          }
        } else {
          // Array of primitives
          flattened[fullKey] = value
            .filter(v => v !== null && v !== undefined)
            .map(v => String(v))
            .join('; ')
        }
      } else if (typeof value === 'object') {
        // Check for circular references or Date objects
        if (value instanceof Date) {
          flattened[fullKey] = value.toISOString()
        } else if (value.constructor && value.constructor.name !== 'Object') {
          // Special object type (Map, Set, etc.)
          flattened[fullKey] = String(value)
        } else {
          // Regular nested object - recurse
          const nestedFlattened = flattenObject(value, fullKey, depth + 1, maxDepth)
          Object.assign(flattened, nestedFlattened)
        }
      } else if (typeof value === 'boolean') {
        flattened[fullKey] = value ? 'true' : 'false'
      } else if (typeof value === 'number') {
        flattened[fullKey] = isNaN(value) || !isFinite(value) ? '' : String(value)
      } else {
        flattened[fullKey] = String(value)
      }
    } catch (error) {
      // Handle any errors gracefully
      flattened[fullKey] = `[Error: ${error instanceof Error ? error.message : 'Unknown'}]`
    }
  }

  return flattened
}

/**
 * Generates CSV content from scene analysis results
 */
export function generateSceneCSV(results: SceneResult[], chunkDuration: number): string {
  const adjustedResults = adjustTimestampsForSequentialVideo(results, chunkDuration)

  // Collect all unique keys from all results
  const allKeys = new Set<string>()
  adjustedResults.forEach((result) => {
    const data = result.result_data || {}
    const scenes = data.scenes || []

    if (scenes.length === 0) {
      const flattened = flattenObject(data)
      Object.keys(flattened).forEach(key => allKeys.add(key))
    } else {
      scenes.forEach((scene: any) => {
        const flattened = flattenObject(scene)
        Object.keys(flattened).forEach(key => allKeys.add(key))
      })
    }
  })

  const dataKeys = Array.from(allKeys).sort()

  // Build header
  const header = [
    'Chunk Index',
    'Chunk Video Start (s)',
    'Chunk Video End (s)',
    'Scene Index',
    'Scene Video Start (s)',
    'Scene Video End (s)',
    'Scene Chunk Start (s)',
    'Scene Chunk End (s)',
    ...dataKeys,
  ]
  const rows: string[][] = [header]

  // Process each result
  adjustedResults.forEach((result) => {
    const metadata = result.result_data?.chunk_metadata
    const data = result.result_data || {}
    const scenes = data.scenes || []

    if (scenes.length === 0) {
      // Flatten chunk-level data
      const flattened = flattenObject(data)

      const row = [
        String(metadata?.chunk_index ?? ''),
        String(metadata?.video_timestamp_start ?? ''),
        String(metadata?.video_timestamp_end ?? ''),
        '',
        '',
        '',
        '',
        '',
      ]

      dataKeys.forEach((key) => {
        row.push(flattened[key] ?? '')
      })

      rows.push(row)
    } else {
      // Add a row for each scene
      scenes.forEach((scene: any, sceneIndex: number) => {
        const flattened = flattenObject(scene)

        const row = [
          String(metadata?.chunk_index ?? ''),
          String(metadata?.video_timestamp_start ?? ''),
          String(metadata?.video_timestamp_end ?? ''),
          String(sceneIndex),
          String(scene.video_start_time ?? scene.video_timestamp ?? ''),
          String(scene.video_end_time ?? ''),
          String(scene.chunk_start_time ?? scene.chunk_timestamp ?? ''),
          String(scene.chunk_end_time ?? ''),
        ]

        dataKeys.forEach((key) => {
          row.push(flattened[key] ?? '')
        })

        rows.push(row)
      })
    }
  })

  // Convert to CSV string
  const csvContent = rows
    .map((row) =>
      row.map((cell) => {
        // Escape quotes and wrap in quotes if contains comma, quote, or newline
        const cellStr = String(cell)
        if (cellStr.includes(',') || cellStr.includes('"') || cellStr.includes('\n')) {
          return `"${cellStr.replace(/"/g, '""')}"`
        }
        return cellStr
      }).join(',')
    )
    .join('\n')

  return csvContent
}

/**
 * Generates JSON export data from scene analysis results
 */
export function generateSceneJSON(
  results: SceneResult[],
  chunkDuration: number,
  jobId: string,
  videoId: string,
  filename?: string
): object {
  const adjustedResults = adjustTimestampsForSequentialVideo(results, chunkDuration)

  return {
    job_id: jobId,
    video_id: videoId,
    filename: filename,
    chunk_duration: chunkDuration,
    total_chunks: results.length,
    results: adjustedResults,
  }
}

/**
 * Triggers a browser download of content
 */
export function downloadFile(content: string | object, filename: string, type: 'csv' | 'json') {
  const mimeType = type === 'csv' ? 'text/csv' : 'application/json'
  const fileContent = typeof content === 'string' ? content : JSON.stringify(content, null, 2)

  const blob = new Blob([fileContent], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
