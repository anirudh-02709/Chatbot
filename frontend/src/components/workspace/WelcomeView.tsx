import React from 'react'
import {
  Code,
  Layers,
  FileText,
  Database,
  ArrowUpRight,
  Sparkles,
} from 'lucide-react'
import type { PromptStarter, ModelStatus } from '@/types'

interface WelcomeViewProps {
  starters: PromptStarter[]
  modelStatus: ModelStatus
  onSelectStarter: (prompt: string) => void
}

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  Engineering: <Code className="w-4 h-4 text-sky-400" />,
  Architecture: <Layers className="w-4 h-4 text-indigo-400" />,
  Documentation: <FileText className="w-4 h-4 text-emerald-400" />,
  Data: <Database className="w-4 h-4 text-amber-400" />,
}

export const WelcomeView: React.FC<WelcomeViewProps> = ({
  starters,
  modelStatus,
  onSelectStarter,
}) => {
  return (
    <div className="flex-1 flex flex-col items-center justify-center max-w-3xl mx-auto px-4 py-8 w-full text-center">
      {/* Intro Header */}
      <div className="mb-7 space-y-2">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-1 border border-surface-border text-xs text-text-secondary mb-2 select-none">
          <Sparkles className="w-3.5 h-3.5 text-accent-base" />
          <span>Local assistant initialized with {modelStatus.name}</span>
        </div>
        <h2 className="text-2xl font-semibold text-text-primary tracking-tight">
          How can I help you today?
        </h2>
        <p className="text-xs text-text-muted max-w-md mx-auto leading-relaxed">
          Select a starting capability below or draft an instruction in the composer to begin a new thread.
        </p>
      </div>

      {/* Starter Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full text-left">
        {starters.map((starter) => {
          const icon = CATEGORY_ICONS[starter.category] || (
            <Code className="w-4 h-4 text-accent-base" />
          )

          return (
            <button
              key={starter.id}
              type="button"
              onClick={() => onSelectStarter(starter.prompt)}
              className="group flex flex-col justify-between p-4 rounded-lg bg-surface-1 hover:bg-surface-2 border border-surface-border hover:border-surface-3 transition-colors duration-100 text-left cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-focus"
            >
              <div className="flex items-center justify-between gap-2 mb-2 w-full">
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 rounded-md bg-surface-2 border border-surface-border/60">
                    {icon}
                  </div>
                  <span className="text-xs font-semibold text-text-primary group-hover:text-accent-hover transition-colors">
                    {starter.title}
                  </span>
                </div>
                <ArrowUpRight className="w-3.5 h-3.5 text-text-dim group-hover:text-text-primary group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
              </div>

              <p className="text-[11px] text-text-muted line-clamp-2 leading-relaxed">
                {starter.description}
              </p>
            </button>
          )
        })}
      </div>
    </div>
  )
}
