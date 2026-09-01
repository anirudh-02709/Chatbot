import React, { useState, useRef, useEffect, useCallback } from 'react'
import { ArrowUp, Square, Paperclip, UploadCloud } from 'lucide-react'
import type { Attachment } from '@/types'
import { fileService } from '@/services/fileService'
import { validateFile, SUPPORTED_FILE_EXTENSIONS } from '@/constants/files'
import { AttachmentChip } from '@/components/workspace/AttachmentChip'
import { cn } from '@/lib/utils'

interface ComposerProps {
  value: string
  onChange: (value: string) => void
  onSend: (attachments?: Attachment[]) => void
  onStop?: () => void
  isGenerating?: boolean
  disabled?: boolean
  placeholder?: string
}

export const Composer: React.FC<ComposerProps> = ({
  value,
  onChange,
  onSend,
  onStop,
  isGenerating = false,
  disabled = false,
  placeholder = 'Draft a question or instruction for Gemma...',
}) => {
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [isDraggingOver, setIsDraggingOver] = useState(false)
  const dragCounterRef = useRef(0)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const abortControllersRef = useRef<Map<string, AbortController>>(new Map())

  // Immediate, snappy textarea auto-sizing without animation lag
  useEffect(() => {
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      const newHeight = Math.min(Math.max(el.scrollHeight, 40), 180)
      el.style.height = `${newHeight}px`
    }
  }, [value])

  // Cleanup pending upload requests on unmount
  useEffect(() => {
    const controllers = abortControllersRef.current
    return () => {
      controllers.forEach((ctrl) => {
        try {
          ctrl.abort()
        } catch {
          // Ignore unmount abort errors
        }
      })
      controllers.clear()
    }
  }, [])

  const handleUploadFiles = useCallback((files: File[]) => {
    if (!files.length) return

    files.forEach((file) => {
      const tempId = `temp_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`
      const validation = validateFile(file)

      if (!validation.valid) {
        // Add failed item directly with validation error
        setAttachments((prev) => [
          ...prev,
          {
            id: tempId,
            name: file.name,
            size: file.size,
            mimeType: file.type || 'application/octet-stream',
            status: 'error',
            errorDetail: validation.error,
          },
        ])
        return
      }

      // Valid file: initialize upload lifecycle
      const abortController = new AbortController()
      abortControllersRef.current.set(tempId, abortController)

      const initialAttachment: Attachment = {
        id: tempId,
        name: file.name,
        size: file.size,
        mimeType: file.type || 'application/octet-stream',
        status: 'uploading',
        progress: 0,
      }

      setAttachments((prev) => [...prev, initialAttachment])

      fileService
        .uploadFile(file, {
          signal: abortController.signal,
          onProgress: (progressPercentage) => {
            setAttachments((prev) =>
              prev.map((att) =>
                att.id === tempId ? { ...att, progress: progressPercentage } : att
              )
            )
          },
        })
        .then((uploaded) => {
          abortControllersRef.current.delete(tempId)
          setAttachments((prev) =>
            prev.map((att) => (att.id === tempId ? uploaded : att))
          )
        })
        .catch((err: unknown) => {
          abortControllersRef.current.delete(tempId)
          if (err instanceof DOMException && err.name === 'AbortError') {
            // Cancelled by user: remove item
            setAttachments((prev) => prev.filter((att) => att.id !== tempId))
            return
          }
          const errorMessage = err instanceof Error ? err.message : 'Upload failed'
          setAttachments((prev) =>
            prev.map((att) =>
              att.id === tempId
                ? { ...att, status: 'error' as const, errorDetail: errorMessage }
                : att
            )
          )
        })
    })
  }, [])

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      handleUploadFiles(Array.from(e.target.files))
    }
    // Reset file input value so the same file can be chosen again if needed
    e.target.value = ''
  }

  const handleRemoveAttachment = useCallback((id: string) => {
    const controller = abortControllersRef.current.get(id)
    if (controller) {
      try {
        controller.abort()
      } catch {
        // Ignore
      }
      abortControllersRef.current.delete(id)
    }
    setAttachments((prev) => prev.filter((att) => att.id !== id))
  }, [])

  // Drag and drop handlers
  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounterRef.current += 1
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDraggingOver(true)
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    e.dataTransfer.dropEffect = 'copy'
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounterRef.current -= 1
    if (dragCounterRef.current <= 0) {
      dragCounterRef.current = 0
      setIsDraggingOver(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounterRef.current = 0
    setIsDraggingOver(false)

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleUploadFiles(Array.from(e.dataTransfer.files))
      e.dataTransfer.clearData()
    }
  }

  const isUploadingAny = attachments.some((att) => att.status === 'uploading')
  const uploadedAttachments = attachments.filter((att) => att.status === 'uploaded')
  const isSendable =
    (value.trim().length > 0 || uploadedAttachments.length > 0) &&
    !disabled &&
    !isGenerating &&
    !isUploadingAny

  const handleSendAction = () => {
    if (!isSendable) return
    onSend(uploadedAttachments.length > 0 ? uploadedAttachments : undefined)
    setAttachments([])
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (isGenerating && onStop) {
        onStop()
      } else if (isSendable) {
        handleSendAction()
      }
    }
  }

  return (
    <div className="w-full max-w-3xl mx-auto px-4 pb-5 pt-1 shrink-0">
      {/* Hidden native file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={SUPPORTED_FILE_EXTENSIONS.join(',')}
        onChange={handleFileInputChange}
        className="hidden"
        tabIndex={-1}
        aria-hidden="true"
      />

      <div
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          'relative rounded-xl border border-surface-border bg-surface-1 shadow-xs transition-all duration-150',
          'focus-within:border-accent-base/80 focus-within:ring-1 focus-within:ring-accent-focus/40',
          isDraggingOver && 'border-accent-base ring-2 ring-accent-focus/40 bg-surface-2/70',
          disabled && !isGenerating && 'opacity-70'
        )}
      >
        {/* Drag & Drop Visual Overlay */}
        {isDraggingOver && (
          <div className="absolute inset-0 z-20 rounded-xl bg-surface-1/90 backdrop-blur-xs flex flex-col items-center justify-center gap-1.5 pointer-events-none border-2 border-dashed border-accent-base animate-in fade-in-50 duration-100">
            <UploadCloud className="w-6 h-6 text-accent-base animate-bounce" />
            <span className="text-xs font-medium text-text-primary">
              Drop files to attach
            </span>
            <span className="text-[10px] text-text-dim">
              Supported: {SUPPORTED_FILE_EXTENSIONS.join(', ')}
            </span>
          </div>
        )}

        {/* Attachment Chips Display Area */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-1.5 px-3.5 pt-3 pb-1 border-b border-surface-border/40">
            {attachments.map((attachment) => (
              <AttachmentChip
                key={attachment.id}
                attachment={attachment}
                onRemove={handleRemoveAttachment}
                disabled={disabled || isGenerating}
              />
            ))}
          </div>
        )}

        {/* Input Area */}
        <div className="px-3.5 pt-2.5 pb-1.5">
          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            disabled={disabled && !isGenerating}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="w-full bg-transparent resize-none text-xs sm:text-sm text-text-primary placeholder:text-text-dim focus:outline-none leading-relaxed max-h-44 disabled:cursor-not-allowed"
            aria-label="Message composer"
          />
        </div>

        {/* Action & Utility Row */}
        <div className="flex items-center justify-between px-3 pb-2.5 pt-1 border-t border-surface-border/40 select-none">
          {/* Left: Attachment & Context */}
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              disabled={disabled || isGenerating || isUploadingAny}
              onClick={() => fileInputRef.current?.click()}
              className="p-1.5 rounded-md text-text-dim hover:text-text-secondary hover:bg-surface-2 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-focus disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
              title="Attach files (PDF, TXT, MD, CSV, JSON, DOCX)"
              aria-label="Attach files"
            >
              <Paperclip className="w-3.5 h-3.5" />
            </button>
            <span className="text-[11px] text-text-dim hidden sm:inline-block">
              {isUploadingAny ? 'Uploading attachments...' : 'Local context only'}
            </span>
          </div>

          {/* Right: Keyboard Hint & Send / Stop Button */}
          <div className="flex items-center gap-2.5">
            <span className="hidden sm:inline-block text-[10px] text-text-dim font-mono">
              {isGenerating
                ? 'Generation in progress'
                : isUploadingAny
                  ? 'Waiting for upload...'
                  : 'Shift+Enter for newline'}
            </span>

            {isGenerating ? (
              <button
                type="button"
                onClick={onStop}
                className="flex items-center justify-center w-7 h-7 rounded-lg bg-surface-3 hover:bg-red-950/40 text-text-primary border border-surface-border hover:border-red-800/60 transition-colors duration-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-focus cursor-pointer"
                aria-label="Stop generation"
                title="Stop generation"
              >
                <Square className="w-3.5 h-3.5 fill-current text-red-400" />
              </button>
            ) : (
              <button
                type="button"
                disabled={!isSendable}
                onClick={handleSendAction}
                className={cn(
                  'flex items-center justify-center w-7 h-7 rounded-lg transition-colors duration-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-focus cursor-pointer',
                  isSendable
                    ? 'bg-accent-base hover:bg-accent-hover text-white'
                    : 'bg-surface-2 text-text-dim cursor-not-allowed border border-surface-border'
                )}
                aria-label="Send message"
              >
                <ArrowUp className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
