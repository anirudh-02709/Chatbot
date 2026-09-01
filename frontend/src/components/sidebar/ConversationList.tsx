import React, { useState, useMemo } from 'react'
import { Search, X } from 'lucide-react'
import { ConversationItem } from './ConversationItem'
import type { Conversation } from '@/types'

interface ConversationListProps {
  conversations: Conversation[]
  activeId: string | null
  onSelectConversation: (id: string) => void
  onDeleteConversation: (id: string) => void
}

function getCategoryForDate(dateStr: string): 'Today' | 'Yesterday' | 'Previous 7 Days' {
  if (!dateStr) return 'Today'
  try {
    const d = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffDays === 0 && d.toDateString() === now.toDateString()) {
      return 'Today'
    }
    if (diffDays <= 1) {
      return 'Yesterday'
    }
    return 'Previous 7 Days'
  } catch {
    return 'Today'
  }
}

export const ConversationList: React.FC<ConversationListProps> = ({
  conversations,
  activeId,
  onSelectConversation,
  onDeleteConversation,
}) => {
  const [searchQuery, setSearchQuery] = useState('')

  const filteredConversations = useMemo(() => {
    if (!searchQuery.trim()) return conversations
    const query = searchQuery.toLowerCase()
    return conversations.filter(
      (c) =>
        c.title.toLowerCase().includes(query) ||
        c.messages.some((m) => m.content.toLowerCase().includes(query))
    )
  }, [conversations, searchQuery])

  // Group dynamically by category
  const groups = useMemo(() => {
    const categories: Array<'Today' | 'Yesterday' | 'Previous 7 Days'> = [
      'Today',
      'Yesterday',
      'Previous 7 Days',
    ]

    return categories
      .map((cat) => ({
        category: cat,
        items: filteredConversations.filter(
          (c) => getCategoryForDate(c.updatedAt || c.createdAt) === cat
        ),
      }))
      .filter((group) => group.items.length > 0)
  }, [filteredConversations])

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Search Input */}
      <div className="px-3 pb-3">
        <div className="relative flex items-center">
          <Search
            className="absolute left-2.5 w-3.5 h-3.5 text-text-dim pointer-events-none"
            aria-hidden="true"
          />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search threads..."
            className="w-full pl-8 pr-7 py-1.5 bg-surface-2/70 hover:bg-surface-2 focus:bg-surface-2 border border-surface-border rounded-md text-xs text-text-primary placeholder:text-text-dim transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-focus"
            aria-label="Search conversation threads"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="absolute right-2 p-0.5 rounded text-text-dim hover:text-text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-focus"
              aria-label="Clear search"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      {/* Grouped Conversations */}
      <div className="flex-1 overflow-y-auto px-2 space-y-4">
        {groups.length > 0 ? (
          groups.map((group) => (
            <div key={group.category} className="space-y-1">
              <h3 className="px-2 text-[10px] font-semibold text-text-dim uppercase tracking-wider select-none">
                {group.category}
              </h3>
              <div className="space-y-0.5">
                {group.items.map((conv) => (
                  <ConversationItem
                    key={conv.id}
                    conversation={conv}
                    isActive={conv.id === activeId}
                    onSelect={onSelectConversation}
                    onDelete={onDeleteConversation}
                  />
                ))}
              </div>
            </div>
          ))
        ) : (
          <div className="px-3 py-6 text-center text-xs text-text-dim">
            {searchQuery ? 'No matching threads' : 'No conversation history'}
          </div>
        )}
      </div>
    </div>
  )
}
