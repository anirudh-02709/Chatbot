import React, { useState, useRef, useEffect } from 'react'
import {
  Menu,
  Share2,
  Trash2,
  SlidersHorizontal,
  ChevronDown,
  Check,
  Cpu,
  Globe,
  Bot,
  MessageSquare,
} from 'lucide-react'
import type { GenerationMode, ModelStatus, AppMode } from '@/types'

interface WorkspaceHeaderProps {
  title: string
  modelStatus: ModelStatus
  generationMode: GenerationMode
  onSelectGenerationMode: (mode: GenerationMode) => void
  appMode: AppMode
  onSelectAppMode: (mode: AppMode) => void
  onToggleSidebar: () => void
}

export const WorkspaceHeader: React.FC<WorkspaceHeaderProps> = ({
  title,
  modelStatus,
  generationMode,
  onSelectGenerationMode,
  appMode,
  onSelectAppMode,
  onToggleSidebar,
}) => {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false)
      }
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsDropdownOpen(false)
      }
    }

    if (isDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      document.addEventListener('keydown', handleKeyDown)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isDropdownOpen])

  const pillLabel =
    generationMode === 'local_gemma'
      ? 'Local Gemma · Local'
      : 'OmniRoute · free-provider-fallback'

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

      {/* Right: Model Selector & Utility Actions */}
      <div className="flex items-center gap-2">
        {/* Mode Segmented Toggle: Chat vs Agent */}
        <div className="flex items-center p-0.5 rounded-lg bg-surface-1 border border-surface-border text-xs">
          <button
            type="button"
            onClick={() => onSelectAppMode('chat')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md font-medium text-xs transition-all cursor-pointer ${
              appMode === 'chat'
                ? 'bg-surface-3 text-text-primary shadow-xs'
                : 'text-text-muted hover:text-text-primary'
            }`}
            title="Chat mode (standard single-turn / RAG)"
            aria-pressed={appMode === 'chat'}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Chat</span>
          </button>
          <button
            type="button"
            onClick={() => onSelectAppMode('agent')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md font-medium text-xs transition-all cursor-pointer ${
              appMode === 'agent'
                ? 'bg-accent-base/15 text-accent-base border border-accent-base/30 shadow-xs'
                : 'text-text-muted hover:text-text-primary'
            }`}
            title="Agent mode (autonomous multi-step tool execution)"
            aria-pressed={appMode === 'agent'}
          >
            <Bot className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Agent</span>
          </button>
        </div>

        {/* Interactive Model Selector Pill */}
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setIsDropdownOpen((prev) => !prev)}
            className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-1 hover:bg-surface-2 active:bg-surface-3 border border-surface-border text-xs text-text-secondary transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-focus"
            aria-haspopup="listbox"
            aria-expanded={isDropdownOpen}
            aria-label="Select generation backend"
          >
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
            <span className="font-medium text-text-primary">
              {pillLabel}
            </span>
            <ChevronDown
              className={`w-3.5 h-3.5 text-text-dim transition-transform duration-150 ${
                isDropdownOpen ? 'rotate-180 text-text-primary' : ''
              }`}
            />
          </button>

          {/* Selector Dropdown Menu */}
          {isDropdownOpen && (
            <div className="absolute right-0 mt-1.5 w-72 rounded-xl bg-surface-1 border border-surface-border shadow-xl py-1.5 z-50 text-xs animate-in fade-in-50 zoom-in-95 duration-100">
              <div className="px-3 py-1.5 border-b border-surface-border-subtle text-[10px] font-semibold text-text-dim uppercase tracking-wider">
                Select Generation Backend
              </div>

              {/* Option 1: OmniRoute */}
              <button
                type="button"
                onClick={() => {
                  onSelectGenerationMode('omniroute')
                  setIsDropdownOpen(false)
                }}
                className={`w-full px-3 py-2 flex items-start gap-2.5 text-left hover:bg-surface-2 transition-colors cursor-pointer ${
                  generationMode === 'omniroute' ? 'bg-surface-2/60' : ''
                }`}
              >
                <div className="p-1 rounded bg-surface-3 border border-surface-border text-accent-base shrink-0 mt-0.5">
                  <Globe className="w-3.5 h-3.5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-text-primary">
                      OmniRoute Gateway
                    </span>
                    <span className="text-[10px] font-mono text-accent-base bg-accent-base/10 px-1.5 py-0.5 rounded border border-accent-base/20">
                      REMOTE
                    </span>
                  </div>
                  <p className="text-[11px] text-text-muted mt-0.5 truncate">
                    free-provider-fallback · Multi-provider
                  </p>
                  <p className="text-[10px] text-text-dim mt-0.5">
                    Gemini → Groq → Cloudflare → OpenRouter
                  </p>
                </div>
                {generationMode === 'omniroute' && (
                  <Check className="w-4 h-4 text-accent-base shrink-0 mt-0.5" />
                )}
              </button>

              {/* Option 2: Local Gemma */}
              <button
                type="button"
                onClick={() => {
                  onSelectGenerationMode('local_gemma')
                  setIsDropdownOpen(false)
                }}
                className={`w-full px-3 py-2 flex items-start gap-2.5 text-left hover:bg-surface-2 transition-colors cursor-pointer ${
                  generationMode === 'local_gemma' ? 'bg-surface-2/60' : ''
                }`}
              >
                <div className="p-1 rounded bg-surface-3 border border-surface-border text-emerald-400 shrink-0 mt-0.5">
                  <Cpu className="w-3.5 h-3.5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-text-primary">
                      Local Gemma (Ollama)
                    </span>
                    <span className="text-[10px] font-mono text-emerald-400 bg-emerald-400/10 px-1.5 py-0.5 rounded border border-emerald-400/20">
                      LOCAL
                    </span>
                  </div>
                  <p className="text-[11px] text-text-muted mt-0.5 truncate">
                    gemma4:e4b · 4B Parameters
                  </p>
                  <p className="text-[10px] text-text-dim mt-0.5">
                    Local on-device inference via Ollama
                  </p>
                </div>
                {generationMode === 'local_gemma' && (
                  <Check className="w-4 h-4 text-accent-base shrink-0 mt-0.5" />
                )}
              </button>
            </div>
          )}
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
