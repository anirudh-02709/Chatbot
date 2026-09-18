import React, { useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  Bot,
  CheckCircle2,
  XCircle,
  Clock,
  RefreshCw,
  AlertTriangle,
} from 'lucide-react'
import type { AgentActivity } from '@/types'

interface AgentActivityViewProps {
  activity: AgentActivity
}

export const AgentActivityView: React.FC<AgentActivityViewProps> = ({ activity }) => {
  const [isExpanded, setIsExpanded] = useState(false)

  const toolCount = activity.tool_calls.length
  const durationSec =
    activity.total_duration_ms !== undefined
      ? (activity.total_duration_ms / 1000).toFixed(2)
      : undefined

  // Status badge config
  const getStatusBadge = () => {
    switch (activity.status) {
      case 'completed':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" />
            Completed
          </span>
        )
      case 'max_iterations_reached':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <AlertTriangle className="w-3 h-3" />
            Max Iterations
          </span>
        )
      case 'loop_detected':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <RefreshCw className="w-3 h-3" />
            Loop Detected
          </span>
        )
      case 'error':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-red-500/10 text-red-400 border border-red-500/20">
            <XCircle className="w-3 h-3" />
            Error
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-surface-3 text-text-muted border border-surface-border">
            {activity.status}
          </span>
        )
    }
  }

  return (
    <div className="my-2 rounded-lg border border-surface-border bg-surface-1/70 overflow-hidden text-xs">
      {/* Header Toggle Button */}
      <button
        type="button"
        onClick={() => setIsExpanded((prev) => !prev)}
        className="w-full px-3 py-2 flex items-center justify-between text-left hover:bg-surface-2/60 transition-colors cursor-pointer select-none"
        aria-expanded={isExpanded}
        aria-label="Toggle agent activity details"
      >
        <div className="flex items-center gap-2 min-w-0">
          <Bot className="w-3.5 h-3.5 text-accent-base shrink-0" />
          <span className="font-medium text-text-primary">Agent activity</span>
          <span className="text-[11px] text-text-dim">
            · {toolCount} {toolCount === 1 ? 'tool used' : 'tools used'}
            {durationSec ? ` · ${durationSec}s` : ''}
          </span>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {getStatusBadge()}
          {isExpanded ? (
            <ChevronDown className="w-3.5 h-3.5 text-text-dim" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-text-dim" />
          )}
        </div>
      </button>

      {/* Expanded Content Details */}
      {isExpanded && (
        <div className="px-3.5 py-3 border-t border-surface-border/60 space-y-3 bg-surface-1/40">
          {/* Summary Stats Grid */}
          <div className="grid grid-cols-3 gap-2 py-1.5 px-2.5 rounded-md bg-surface-2/50 border border-surface-border/50 text-[11px]">
            <div>
              <span className="block text-text-dim text-[10px] uppercase font-semibold tracking-wider">
                Status
              </span>
              <span className="font-mono capitalize text-text-primary">
                {activity.status.replace(/_/g, ' ')}
              </span>
            </div>
            <div>
              <span className="block text-text-dim text-[10px] uppercase font-semibold tracking-wider">
                Iterations
              </span>
              <span className="font-mono text-text-primary">
                {activity.iteration_count}
              </span>
            </div>
            <div>
              <span className="block text-text-dim text-[10px] uppercase font-semibold tracking-wider">
                Duration
              </span>
              <span className="font-mono text-text-primary">
                {durationSec ? `${durationSec}s` : 'N/A'}
              </span>
            </div>
          </div>

          {/* Tools Executed List */}
          <div>
            <div className="text-[10px] font-semibold text-text-dim uppercase tracking-wider mb-1.5">
              Tools Used ({toolCount})
            </div>

            {toolCount === 0 ? (
              <p className="text-[11px] text-text-muted italic">
                Direct answer produced without invoking tools.
              </p>
            ) : (
              <div className="space-y-1.5">
                {activity.tool_calls.map((tc, idx) => (
                  <div
                    key={`${tc.tool_name}-${idx}`}
                    className="flex items-start justify-between gap-2 p-2 rounded-md bg-surface-2/40 border border-surface-border/40 text-[11px]"
                  >
                    <div className="flex items-start gap-2 min-w-0">
                      <span className="font-mono text-[10px] text-text-dim mt-0.5">
                        {idx + 1}.
                      </span>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="font-semibold text-text-primary font-mono">
                            {tc.tool_name}
                          </span>
                          {tc.success ? (
                            <span className="inline-flex items-center gap-0.5 text-[10px] text-emerald-400">
                              <CheckCircle2 className="w-3 h-3" />
                              completed
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-0.5 text-[10px] text-red-400">
                              <XCircle className="w-3 h-3" />
                              failed {tc.error_type ? `(${tc.error_type})` : ''}
                            </span>
                          )}
                        </div>

                        {tc.arguments && Object.keys(tc.arguments).length > 0 && (
                          <div className="mt-1 font-mono text-[10px] text-text-dim bg-surface-3/60 px-2 py-1 rounded border border-surface-border/40 truncate max-w-md">
                            {JSON.stringify(tc.arguments)}
                          </div>
                        )}
                      </div>
                    </div>

                    {tc.duration_ms !== undefined && (
                      <div className="flex items-center gap-1 text-[10px] font-mono text-text-dim shrink-0">
                        <Clock className="w-3 h-3" />
                        <span>{tc.duration_ms.toFixed(1)}ms</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
