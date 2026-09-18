import React from 'react'
import {
  Plus,
  Settings,
  HelpCircle,
  Cpu,
  X,
} from 'lucide-react'
import { ConversationList } from './ConversationList'
import type { Conversation, GenerationMode, ModelStatus } from '@/types'

interface SidebarProps {
  conversations: Conversation[]
  activeConversationId: string | null
  modelStatus: ModelStatus
  generationMode?: GenerationMode
  onSelectConversation: (id: string) => void
  onDeleteConversation: (id: string) => void
  onNewConversation: () => void
  onCloseMobile?: () => void
}

export const Sidebar: React.FC<SidebarProps> = ({
  conversations,
  activeConversationId,
  modelStatus,
  generationMode = 'omniroute',
  onSelectConversation,
  onDeleteConversation,
  onNewConversation,
  onCloseMobile,
}) => {
  const runtimeLabel = generationMode === 'local_gemma' ? 'LOCAL' : 'OMNIROUTE'
  const modelDisplayName =
    generationMode === 'local_gemma'
      ? modelStatus.name || 'Gemma 4 E4B'
      : modelStatus.name || 'free-provider-fallback'
  return (
    <aside className="flex flex-col h-full w-64 bg-surface-1 border-r border-surface-border select-none">
      {/* Brand Header */}
      <div className="flex items-center justify-between p-3 border-b border-surface-border-subtle">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center w-7 h-7 rounded-md bg-surface-2 border border-surface-border text-accent-base">
            <Cpu className="w-4 h-4" />
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-semibold text-text-primary tracking-tight">
              Chatbot
            </span>
            <span className="text-[10px] text-text-dim">
              Local Assistant
            </span>
          </div>
        </div>

        {/* Mobile Close Button */}
        {onCloseMobile && (
          <button
            type="button"
            onClick={onCloseMobile}
            className="md:hidden p-1.5 rounded-md hover:bg-surface-2 text-text-muted hover:text-text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-focus"
            aria-label="Close navigation"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* New Thread Action */}
      <div className="p-3">
        <button
          type="button"
          onClick={() => {
            onNewConversation()
            if (onCloseMobile) onCloseMobile()
          }}
          className="w-full flex items-center justify-between px-3 py-2 bg-surface-2 hover:bg-surface-3 active:bg-surface-3 text-text-primary border border-surface-border rounded-md text-xs font-medium transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-focus group"
        >
          <span className="flex items-center gap-2">
            <Plus className="w-3.5 h-3.5 text-accent-base group-hover:scale-105 transition-transform" />
            New Thread
          </span>
          <kbd className="hidden sm:inline-block px-1.5 py-0.5 text-[10px] font-mono text-text-dim bg-surface-1 border border-surface-border rounded">
            Ctrl+N
          </kbd>
        </button>
      </div>

      {/* Conversation History */}
      <ConversationList
        conversations={conversations}
        activeId={activeConversationId}
        onSelectConversation={(id) => {
          onSelectConversation(id)
          if (onCloseMobile) onCloseMobile()
        }}
        onDeleteConversation={onDeleteConversation}
      />

      {/* Lower Utility Area */}
      <div className="p-3 border-t border-surface-border bg-surface-1/60 space-y-2">
        {/* Model Indicator (Static, no pulse) */}
        <div className="flex items-center justify-between px-2.5 py-1.5 rounded-md bg-surface-2/60 border border-surface-border-subtle text-[11px]">
          <div className="flex items-center gap-1.5 min-w-0">
            <span
              className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                modelStatus.status === 'ready'
                  ? 'bg-status-ready'
                  : modelStatus.status === 'offline'
                  ? 'bg-status-error'
                  : 'bg-status-warning animate-pulse'
              }`}
              aria-hidden="true"
            />
            <span className="truncate text-text-secondary font-medium">
              {modelDisplayName}
            </span>
          </div>
          <span className="text-[10px] font-mono text-text-dim uppercase">
            {runtimeLabel}
          </span>
        </div>

        {/* Settings & Help Triggers */}
        <div className="flex items-center justify-between pt-0.5 px-1">
          <button
            type="button"
            className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text-primary py-1 px-1.5 rounded-md hover:bg-surface-2 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-focus cursor-pointer"
            title="Application Settings"
            aria-label="Settings"
          >
            <Settings className="w-3.5 h-3.5" />
            <span>Settings</span>
          </button>

          <button
            type="button"
            className="p-1.5 rounded-md text-text-muted hover:text-text-primary hover:bg-surface-2 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-focus cursor-pointer"
            title="Help & Shortcuts"
            aria-label="Help"
          >
            <HelpCircle className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </aside>
  )
}
