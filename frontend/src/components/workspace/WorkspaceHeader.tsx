import React from 'react'
import {
  Menu,
  Share2,
  Trash2,
  SlidersHorizontal,
} from 'lucide-react'
import type { ModelStatus } from '@/types'

interface WorkspaceHeaderProps {
  title: string
  modelStatus: ModelStatus
  onToggleSidebar: () => void
}

export const WorkspaceHeader: React.FC<WorkspaceHeaderProps> = ({
  title,
  modelStatus,
  onToggleSidebar,
}) => {
  return (
    <header className="h-13 px-4 border-b border-surface-border bg-surface-0 flex items-center justify-between shrink-0 z-10 select-none">
      {/* Left: Mobile Menu Toggle & Title */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="md:hidden p-1.5 rounded-md hover:bg-surface-2 text-text-muted hover:text-text-primary transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-focus cursor-pointer"
          aria-label="Toggle navigation menu"
        >
          <Menu className="w-4 h-4" />
        </button>

        <h1 className="text-sm font-semibold text-text-primary truncate max-w-xs sm:max-w-md">
          {title}
        </h1>
      </div>

      {/* Right: Model Indicator & Utility Actions */}
      <div className="flex items-center gap-2">
        {/* Model Status Pill (Static indicator) */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-1 border border-surface-border text-xs text-text-secondary">
          <span
            className="w-1.5 h-1.5 rounded-full bg-status-ready shrink-0"
            aria-hidden="true"
          />
          <span className="font-medium text-text-primary">
            {modelStatus.name}
          </span>
          <span className="text-text-dim text-[11px]">·</span>
          <span className="text-text-muted text-[11px]">
            {modelStatus.runtime === 'local' ? 'Local' : 'Remote'}
          </span>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-0.5">
          <button
            type="button"
            className="p-2 rounded-md hover:bg-surface-2 text-text-dim hover:text-text-primary transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-focus cursor-pointer"
            title="Parameters"
            aria-label="Parameters"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            className="p-2 rounded-md hover:bg-surface-2 text-text-dim hover:text-text-primary transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-focus cursor-pointer"
            title="Export conversation"
            aria-label="Export conversation"
          >
            <Share2 className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            className="p-2 rounded-md hover:bg-surface-2 text-text-dim hover:text-text-primary transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-focus cursor-pointer"
            title="Clear thread"
            aria-label="Clear thread"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </header>
  )
}
