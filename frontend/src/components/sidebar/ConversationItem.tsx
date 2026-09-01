import React from 'react'
import { MessageSquare, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Conversation } from '@/types'

interface ConversationItemProps {
  conversation: Conversation
  isActive: boolean
  onSelect: (id: string) => void
  onDelete: (id: string) => void
}

function formatDisplayDate(dateStr: string): string {
  if (!dateStr) return ''
  // If it's already a short time string (e.g. "10:42 AM", "Yesterday")
  if (dateStr.length < 12) return dateStr
  try {
    const d = new Date(dateStr)
    const now = new Date()
    const isToday = d.toDateString() === now.toDateString()
    if (isToday) {
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
  } catch {
    return dateStr
  }
}

export const ConversationItem: React.FC<ConversationItemProps> = ({
  conversation,
  isActive,
  onSelect,
  onDelete,
}) => {
  const displayTime = formatDisplayDate(conversation.updatedAt || conversation.createdAt)

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onSelect(conversation.id)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onSelect(conversation.id)
        }
      }}
      className={cn(
        'group relative flex items-center justify-between gap-2.5 px-3 py-2 rounded-md text-xs transition-colors duration-100 cursor-pointer select-none text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-focus',
        isActive
          ? 'bg-surface-2 text-text-primary font-medium border border-surface-border'
          : 'text-text-secondary hover:bg-surface-2/60 hover:text-text-primary border border-transparent'
      )}
      aria-current={isActive ? 'page' : undefined}
    >
      {/* Restrained Active Indicator */}
      {isActive && (
        <span
          className="absolute left-0 top-2 bottom-2 w-0.5 bg-accent-base rounded-r-full"
          aria-hidden="true"
        />
      )}

      <div className="flex items-center gap-2.5 min-w-0 flex-1">
        <MessageSquare
          className={cn(
            'w-3.5 h-3.5 shrink-0 transition-colors',
            isActive ? 'text-accent-base' : 'text-text-dim group-hover:text-text-secondary'
          )}
          aria-hidden="true"
        />
        <span className="truncate" title={conversation.title}>
          {conversation.title}
        </span>
      </div>

      <div className="flex items-center gap-1 shrink-0">
        <span className="text-[11px] text-text-dim group-hover:text-text-muted font-mono">
          {displayTime}
        </span>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onDelete(conversation.id)
          }}
          className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 p-1 rounded hover:bg-surface-3 text-text-dim hover:text-red-300 transition-opacity focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-focus cursor-pointer"
          aria-label={`Delete ${conversation.title}`}
          title="Delete conversation"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}
