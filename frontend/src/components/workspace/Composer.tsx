import React, { useRef, useEffect } from 'react'
import { ArrowUp, Square, Paperclip } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ComposerProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
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
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Immediate, snappy textarea auto-sizing without animation lag
  useEffect(() => {
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      const newHeight = Math.min(Math.max(el.scrollHeight, 40), 180)
      el.style.height = `${newHeight}px`
    }
  }, [value])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (isGenerating && onStop) {
        onStop()
      } else if (value.trim() && !disabled) {
        onSend()
      }
    }
  }

  const isSendable = value.trim().length > 0 && !disabled && !isGenerating

  return (
    <div className="w-full max-w-3xl mx-auto px-4 pb-5 pt-1 shrink-0">
      <div
        className={cn(
          'relative rounded-xl border border-surface-border bg-surface-1 shadow-xs transition-colors duration-100',
          'focus-within:border-accent-base/80 focus-within:ring-1 focus-within:ring-accent-focus/40',
          disabled && !isGenerating && 'opacity-70'
        )}
      >
        {/* Input Area */}
        <div className="px-3.5 pt-3 pb-1.5">
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
              disabled={disabled || isGenerating}
              className="p-1.5 rounded-md text-text-dim hover:text-text-secondary hover:bg-surface-2 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-focus disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
              title="Attach context file (placeholder)"
              aria-label="Attach file"
            >
              <Paperclip className="w-3.5 h-3.5" />
            </button>
            <span className="text-[11px] text-text-dim hidden sm:inline-block">
              Local context only
            </span>
          </div>

          {/* Right: Keyboard Hint & Send / Stop Button */}
          <div className="flex items-center gap-2.5">
            <span className="hidden sm:inline-block text-[10px] text-text-dim font-mono">
              {isGenerating ? 'Generation in progress' : 'Shift+Enter for newline'}
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
                onClick={onSend}
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
