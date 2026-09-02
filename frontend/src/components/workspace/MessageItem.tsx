import React, { useState } from 'react'
import {
  Cpu,
  User,
  Copy,
  Check,
  RotateCw,
  AlertCircle,
} from 'lucide-react'
import type { Message } from '@/types'
import { AttachmentChip } from '@/components/workspace/AttachmentChip'
import { MarkdownRenderer } from '@/components/workspace/MarkdownRenderer'

interface MessageItemProps {
  message: Message
  isLatestAssistant?: boolean
  onRegenerate?: () => void
}

export const MessageItem: React.FC<MessageItemProps> = ({
  message,
  isLatestAssistant = false,
  onRegenerate,
}) => {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'
  const isGenerating = message.status === 'generating'
  const isError = message.status === 'error'
  const hasAttachments = Boolean(message.attachments && message.attachments.length > 0)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback
    }
  }

  if (isUser) {
    return (
      <div className="flex justify-end w-full py-1.5">
        <div className="flex items-start gap-2.5 max-w-2xl">
          <div className="rounded-lg bg-surface-2 border border-surface-border px-4 py-2.5 text-xs sm:text-sm text-text-primary shadow-xs space-y-2">
            {hasAttachments && (
              <div className="flex flex-wrap gap-1.5 pb-1 border-b border-surface-border/50">
                {message.attachments!.map((att) => (
                  <AttachmentChip
                    key={att.id}
                    attachment={att}
                    className="bg-surface-3/80 border-surface-border/80"
                  />
                ))}
              </div>
            )}
            {message.content && (
              <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
            )}
            <span className="block text-[10px] text-text-dim text-right mt-1 font-mono">
              {message.createdAt}
            </span>
          </div>
          <div className="flex items-center justify-center w-6 h-6 rounded-md bg-surface-2 border border-surface-border text-text-muted shrink-0 mt-0.5">
            <User className="w-3.5 h-3.5" />
          </div>
        </div>
      </div>
    )
  }

  // Assistant Message
  return (
    <div className="flex items-start gap-3 w-full py-3 group">
      {/* Assistant Avatar */}
      <div className="flex items-center justify-center w-7 h-7 rounded-md bg-surface-2 border border-surface-border text-accent-base shrink-0 mt-0.5">
        <Cpu className="w-4 h-4" />
      </div>

      {/* Content Container */}
      <div className="flex-1 min-w-0 space-y-2">
        {/* Header / Role Info */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-text-primary">
            Gemma 4 E4B
          </span>
          <span className="text-[10px] text-text-dim font-mono">
            {message.createdAt}
          </span>
        </div>

        {/* Message Content */}
        <div className="text-xs sm:text-sm text-text-secondary">
          {message.content ? (
            <MarkdownRenderer content={message.content} />
          ) : isGenerating ? (
            <div className="flex items-center gap-1.5 py-1 text-xs text-text-muted">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-base animate-pulse" />
              <span>Generating response...</span>
            </div>
          ) : null}

          {/* Generating Stream Cursor */}
          {isGenerating && message.content && (
            <span className="inline-block w-1.5 h-3.5 ml-1 bg-accent-base animate-pulse align-middle" />
          )}
        </div>

        {/* Error Alert Box */}
        {isError && (
          <div className="flex items-center justify-between gap-3 p-3 rounded-md bg-red-950/30 border border-red-900/50 text-xs text-red-300">
            <div className="flex items-center gap-2 min-w-0">
              <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
              <span className="truncate">
                {message.errorDetail || 'Failed to generate response. Please try again.'}
              </span>
            </div>
            {onRegenerate && (
              <button
                type="button"
                onClick={onRegenerate}
                className="px-2.5 py-1 rounded bg-red-900/50 hover:bg-red-800/60 border border-red-700/50 text-[11px] font-medium text-red-200 transition-colors cursor-pointer shrink-0"
              >
                Retry
              </button>
            )}
          </div>
        )}

        {/* Action Toolbar (Copy & Regenerate) */}
        {!isGenerating && !isError && message.content && (
          <div className="flex items-center gap-1 pt-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] text-text-dim hover:text-text-primary hover:bg-surface-2 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-focus cursor-pointer"
              title="Copy message text"
              aria-label="Copy message"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3 text-emerald-400" />
                  <span className="text-emerald-400">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  <span>Copy</span>
                </>
              )}
            </button>

            {isLatestAssistant && onRegenerate && (
              <button
                type="button"
                onClick={onRegenerate}
                className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] text-text-dim hover:text-text-primary hover:bg-surface-2 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-focus cursor-pointer"
                title="Regenerate response"
                aria-label="Regenerate response"
              >
                <RotateCw className="w-3 h-3" />
                <span>Regenerate</span>
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
