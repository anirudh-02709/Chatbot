import React, { useRef, useEffect } from 'react'
import { MessageItem } from './MessageItem'
import type { Message } from '@/types'

interface MessageListProps {
  messages: Message[]
  isGenerating: boolean
  onRegenerate: () => void
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  isGenerating,
  onRegenerate,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const bottomAnchorRef = useRef<HTMLDivElement>(null)
  const userScrolledUpRef = useRef<boolean>(false)

  // Track if user manually scrolled up
  const handleScroll = () => {
    const el = containerRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    userScrolledUpRef.current = distanceFromBottom > 120
  }

  // Auto-scroll when new messages arrive or stream updates (unless user scrolled up)
  useEffect(() => {
    if (!userScrolledUpRef.current && bottomAnchorRef.current) {
      bottomAnchorRef.current.scrollIntoView({ behavior: 'auto' })
    }
  }, [messages, isGenerating])

  const latestAssistantId = [...messages]
    .reverse()
    .find((m) => m.role === 'assistant')?.id

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto px-4 py-6 w-full"
    >
      <div className="max-w-3xl mx-auto space-y-4">
        {messages.map((message) => (
          <MessageItem
            key={message.id}
            message={message}
            isLatestAssistant={message.id === latestAssistantId}
            onRegenerate={onRegenerate}
          />
        ))}
        <div ref={bottomAnchorRef} className="h-1" />
      </div>
    </div>
  )
}
