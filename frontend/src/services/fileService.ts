import type { Attachment } from '@/types'
import { validateFile } from '@/constants/files'

export interface UploadFileOptions {
  onProgress?: (progressPercentage: number) => void
  signal?: AbortSignal
}

export interface FileConfig {
  maxUploadSizeBytes: number
  maxUploadSizeMb: number
  allowedExtensions: string[]
  allowedMimeTypes: string[]
}

export class FileService {
  /**
   * Upload a single file to the backend storage endpoint.
   * Provides genuine byte-level upload progress tracking via XMLHttpRequest.
   */
  async uploadFile(file: File, options: UploadFileOptions = {}): Promise<Attachment> {
    const { onProgress, signal } = options

    // Client-side pre-validation
    const validation = validateFile(file)
    if (!validation.valid) {
      throw new Error(validation.error || 'Invalid file.')
    }

    if (signal?.aborted) {
      throw new DOMException('Upload aborted by user.', 'AbortError')
    }

    return new Promise<Attachment>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      const formData = new FormData()
      formData.append('file', file)

      // Handle abort signal
      const abortHandler = () => {
        xhr.abort()
        reject(new DOMException('Upload aborted by user.', 'AbortError'))
      }

      if (signal) {
        signal.addEventListener('abort', abortHandler, { once: true })
      }

      // Track genuine byte-level progress
      if (xhr.upload && onProgress) {
        xhr.upload.onprogress = (event: ProgressEvent) => {
          if (event.lengthComputable && event.total > 0) {
            const percent = Math.min(100, Math.round((event.loaded / event.total) * 100))
            onProgress(percent)
          }
        }
      }

      xhr.onload = () => {
        if (signal) {
          signal.removeEventListener('abort', abortHandler)
        }

        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText)
            const attachment: Attachment = {
              id: data.id,
              name: data.name || file.name,
              size: typeof data.size === 'number' ? data.size : file.size,
              mimeType: data.mimeType || file.type || 'application/octet-stream',
              status: 'uploaded',
              uploadedAt: data.uploadedAt || new Date().toISOString(),
              progress: 100,
            }
            resolve(attachment)
          } catch {
            reject(new Error('Failed to parse server upload response.'))
          }
        } else {
          let errorMessage = `Upload failed with status ${xhr.status}`
          try {
            const errJson = JSON.parse(xhr.responseText)
            if (errJson.detail) {
              errorMessage = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail)
            }
          } catch {
            // Keep default error message
          }
          reject(new Error(errorMessage))
        }
      }

      xhr.onerror = () => {
        if (signal) {
          signal.removeEventListener('abort', abortHandler)
        }
        reject(new Error('Network error during file upload.'))
      }

      xhr.onabort = () => {
        if (signal) {
          signal.removeEventListener('abort', abortHandler)
        }
        reject(new DOMException('Upload aborted.', 'AbortError'))
      }

      xhr.open('POST', '/api/files/upload')
      xhr.send(formData)
    })
  }

  /**
   * Fetch file upload configuration from backend.
   */
  async fetchFileConfig(): Promise<FileConfig> {
    const res = await fetch('/api/files/config')
    if (!res.ok) {
      throw new Error(`Failed to fetch file configuration: ${res.status}`)
    }
    return res.json()
  }
}

export const fileService = new FileService()
