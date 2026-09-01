import React from 'react'
import {
  FileText,
  FileCode,
  FileSpreadsheet,
  File,
  X,
  AlertCircle,
  Loader2,
  Check,
} from 'lucide-react'
import type { Attachment } from '@/types'
import { formatFileSize, getFileExtension } from '@/constants/files'
import { cn } from '@/lib/utils'

interface AttachmentChipProps {
  attachment: Attachment
  onRemove?: (id: string) => void
  disabled?: boolean
  className?: string
}

function getFileIcon(filename: string) {
  const ext = getFileExtension(filename)
  switch (ext) {
    case '.pdf':
    case '.docx':
    case '.txt':
    case '.md':
      return <FileText className="w-3.5 h-3.5 text-accent-base shrink-0" />
    case '.csv':
      return <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
    case '.json':
      return <FileCode className="w-3.5 h-3.5 text-amber-400 shrink-0" />
    default:
      return <File className="w-3.5 h-3.5 text-text-dim shrink-0" />
  }
}

export const AttachmentChip: React.FC<AttachmentChipProps> = ({
  attachment,
  onRemove,
  disabled = false,
  className,
}) => {
  const isUploading = attachment.status === 'uploading'
  const isError = attachment.status === 'error'
  const isUploaded = attachment.status === 'uploaded'

  return (
    <div
      className={cn(
        'relative group/chip inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs',
        'bg-surface-2/90 border border-surface-border shadow-2xs transition-all duration-100',
        isError && 'border-red-800/60 bg-red-950/20 text-red-300',
        isUploading && 'border-accent-focus/40 bg-surface-2',
        className
      )}
      title={isError ? attachment.errorDetail || 'Upload failed' : `${attachment.name} (${formatFileSize(attachment.size)})`}
    >
      {/* File Type Icon */}
      {isUploading ? (
        <Loader2 className="w-3.5 h-3.5 text-accent-base animate-spin shrink-0" />
      ) : isError ? (
        <AlertCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />
      ) : (
        getFileIcon(attachment.name)
      )}

      {/* File Info */}
      <div className="flex flex-col min-w-0 max-w-[150px] sm:max-w-[200px]">
        <span className="truncate font-medium text-text-primary text-[11px] leading-tight">
          {attachment.name}
        </span>
        <div className="flex items-center gap-1 text-[10px] text-text-dim leading-none mt-0.5">
          <span>{formatFileSize(attachment.size)}</span>
          {isUploading && typeof attachment.progress === 'number' && (
            <span className="text-accent-base font-mono">· {attachment.progress}%</span>
          )}
          {isUploaded && (
            <span className="inline-flex items-center text-emerald-400 font-mono">
              <Check className="w-2.5 h-2.5 mr-0.5" />
            </span>
          )}
          {isError && (
            <span className="text-red-400 truncate">
              · {attachment.errorDetail || 'Failed'}
            </span>
          )}
        </div>
      </div>

      {/* Upload Progress Bar (Embedded underneath) */}
      {isUploading && typeof attachment.progress === 'number' && (
        <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-surface-3 rounded-b-lg overflow-hidden">
          <div
            className="h-full bg-accent-base transition-all duration-150 ease-out"
            style={{ width: `${attachment.progress}%` }}
          />
        </div>
      )}

      {/* Remove Button */}
      {onRemove && (
        <button
          type="button"
          disabled={disabled}
          onClick={(e) => {
            e.stopPropagation()
            onRemove(attachment.id)
          }}
          className={cn(
            'p-0.5 rounded text-text-dim hover:text-text-primary hover:bg-surface-3 transition-colors',
            'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-focus cursor-pointer shrink-0 ml-0.5',
            disabled && 'cursor-not-allowed opacity-50'
          )}
          aria-label={`Remove ${attachment.name}`}
          title="Remove attachment"
        >
          <X className="w-3 h-3" />
        </button>
      )}
    </div>
  )
}
