export const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024 // 10 MB
export const MAX_FILE_SIZE_MB = 10

export const SUPPORTED_FILE_EXTENSIONS = [
  '.pdf',
  '.txt',
  '.md',
  '.csv',
  '.json',
  '.docx',
] as const

export type SupportedFileExtension = (typeof SUPPORTED_FILE_EXTENSIONS)[number]

export const SUPPORTED_MIME_TYPES = [
  'application/pdf',
  'text/plain',
  'text/markdown',
  'text/x-markdown',
  'text/csv',
  'application/csv',
  'application/json',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
] as const

export function formatFileSize(bytes: number): string {
  if (bytes <= 0) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function getFileExtension(filename: string): string {
  const lastDot = filename.lastIndexOf('.')
  if (lastDot === -1) return ''
  return filename.slice(lastDot).toLowerCase()
}

export function isSupportedExtension(extension: string): extension is SupportedFileExtension {
  return SUPPORTED_FILE_EXTENSIONS.includes(extension.toLowerCase() as SupportedFileExtension)
}

export function isSupportedFileType(filename: string, mimeType?: string): boolean {
  const ext = getFileExtension(filename)
  if (isSupportedExtension(ext)) return true
  if (mimeType && (SUPPORTED_MIME_TYPES as readonly string[]).includes(mimeType.toLowerCase())) {
    return true
  }
  return false
}

export function validateFile(file: File): { valid: boolean; error?: string } {
  if (file.size === 0) {
    return {
      valid: false,
      error: `File "${file.name}" is empty (0 bytes).`,
    }
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    return {
      valid: false,
      error: `File "${file.name}" exceeds the maximum size limit of ${MAX_FILE_SIZE_MB} MB.`,
    }
  }

  if (!isSupportedFileType(file.name, file.type)) {
    return {
      valid: false,
      error: `File "${file.name}" has an unsupported format. Supported formats: ${SUPPORTED_FILE_EXTENSIONS.join(', ')}`,
    }
  }

  return { valid: true }
}
