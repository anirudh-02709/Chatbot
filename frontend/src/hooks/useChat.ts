import { useState, useRef, useCallback, useEffect } from 'react'
import type {
  Conversation,
  Message,
  ChatResponseProvider,
} from '@/types'
import { MOCK_CONVERSATIONS } from '@/data/mockData'
import { BackendResponseProvider } from '@/services/backendResponseService'

const defaultProvider = new BackendResponseProvider()

function deriveTitleFromPrompt(prompt: string): string {
  const clean = prompt.replace(/\s+/g, ' ').trim()
  if (clean.length <= 36) return clean
  const words = clean.split(' ')
  let title = ''
  for (const word of words) {
    if ((title + ' ' + word).trim().length > 36) break
    title = (title + ' ' + word).trim()
  }
  return title || clean.slice(0, 36) + '...'
}

function formatCurrentTime(): string {
  const now = new Date()
  return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function useChat(provider: ChatResponseProvider = defaultProvider) {
  const [conversations, setConversations] = useState<Conversation[]>(MOCK_CONVERSATIONS)
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)

  // Track active stream abort controller
  const abortCurrentStream = useRef<(() => void) | null>(null)

  // Streaming chunk batch buffer (frame-aligned via requestAnimationFrame)
  const pendingChunksRef = useRef<Map<string, string>>(new Map())
  const rafIdRef = useRef<number | null>(null)

  // Flush pending streaming chunk buffer into React state
  const flushPendingChunks = useCallback(() => {
    if (rafIdRef.current !== null && typeof window !== 'undefined') {
      window.cancelAnimationFrame(rafIdRef.current)
      rafIdRef.current = null
    }
    if (pendingChunksRef.current.size === 0) return

    const chunkEntries = Array.from(pendingChunksRef.current.entries())
    pendingChunksRef.current.clear()

    setConversations((prev) =>
      prev.map((conv) => {
        let convUpdated = false
        const updatedMessages = conv.messages.map((m) => {
          const chunkToAdd = chunkEntries.find(([msgId]) => msgId === m.id)?.[1]
          if (chunkToAdd) {
            convUpdated = true
            return { ...m, content: m.content + chunkToAdd }
          }
          return m
        })
        return convUpdated ? { ...conv, messages: updatedMessages } : conv
      })
    )
  }, [])

  // Queue a chunk for frame-aligned batched update
  const queueChunk = useCallback(
    (messageId: string, chunk: string) => {
      const prevBuf = pendingChunksRef.current.get(messageId) || ''
      pendingChunksRef.current.set(messageId, prevBuf + chunk)

      if (rafIdRef.current === null && typeof window !== 'undefined') {
        rafIdRef.current = window.requestAnimationFrame(() => {
          rafIdRef.current = null
          flushPendingChunks()
        })
      }
    },
    [flushPendingChunks]
  )

  // Active conversation helper
  const activeConversation = conversations.find((c) => c.id === activeConversationId)
  const messages = activeConversation ? activeConversation.messages : []

  // Abort active stream and clean up state across all conversations
  const abortActiveGeneration = useCallback(() => {
    if (abortCurrentStream.current) {
      abortCurrentStream.current()
      abortCurrentStream.current = null
    }
    flushPendingChunks()
    setIsGenerating(false)

    // Mark any currently generating message as complete across conversations to preserve partial content
    setConversations((prev) =>
      prev.map((conv) => {
        const hasGenerating = conv.messages.some((m) => m.status === 'generating')
        if (!hasGenerating) return conv
        return {
          ...conv,
          messages: conv.messages.map((m) => {
            if (m.status === 'generating') {
              return { ...m, status: 'complete' }
            }
            return m
          }),
        }
      })
    )
  }, [flushPendingChunks])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortCurrentStream.current) {
        abortCurrentStream.current()
      }
      if (rafIdRef.current !== null && typeof window !== 'undefined') {
        window.cancelAnimationFrame(rafIdRef.current)
      }
    }
  }, [])

  const stopGeneration = useCallback(() => {
    abortActiveGeneration()
  }, [abortActiveGeneration])

  const createConversation = useCallback(() => {
    abortActiveGeneration()
    setActiveConversationId(null)
  }, [abortActiveGeneration])

  const selectConversation = useCallback(
    (id: string) => {
      abortActiveGeneration()
      setActiveConversationId(id)
    },
    [abortActiveGeneration]
  )

  const sendMessage = useCallback(
    (content: string) => {
      const trimmed = content.trim()
      if (!trimmed || isGenerating) return

      const timeStr = formatCurrentTime()
      const timestamp = Date.now()
      const userMessageId = `msg-u-${timestamp}`
      const assistantMessageId = `msg-a-${timestamp}`

      const newUserMessage: Message = {
        id: userMessageId,
        role: 'user',
        content: trimmed,
        createdAt: timeStr,
        status: 'complete',
      }

      const initialAssistantMessage: Message = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        createdAt: timeStr,
        status: 'generating',
      }

      let currentConvId = activeConversationId
      const currentHistory = activeConversation ? activeConversation.messages : []

      if (!currentConvId) {
        // Create new conversation
        currentConvId = `conv-${timestamp}`
        const derivedTitle = deriveTitleFromPrompt(trimmed)
        const nowISO = new Date().toISOString()

        const newConversation: Conversation = {
          id: currentConvId,
          title: derivedTitle,
          createdAt: nowISO,
          updatedAt: nowISO,
          messages: [newUserMessage, initialAssistantMessage],
        }

        setConversations((prev) => [newConversation, ...prev])
        setActiveConversationId(currentConvId)
      } else {
        // Append to existing active conversation
        setConversations((prev) =>
          prev.map((conv) => {
            if (conv.id !== currentConvId) return conv
            return {
              ...conv,
              updatedAt: new Date().toISOString(),
              messages: [...conv.messages, newUserMessage, initialAssistantMessage],
            }
          })
        )
      }

      setIsGenerating(true)

      const targetConvId = currentConvId

      const cancelFn = provider.streamResponse(
        trimmed,
        currentHistory,
        {
          onChunk: (chunk: string) => {
            queueChunk(assistantMessageId, chunk)
          },
          onError: (err: Error) => {
            flushPendingChunks()
            setIsGenerating(false)
            abortCurrentStream.current = null
            setConversations((prev) =>
              prev.map((conv) => {
                if (conv.id !== targetConvId) return conv
                return {
                  ...conv,
                  messages: conv.messages.map((m) => {
                    if (m.id !== assistantMessageId) return m
                    return {
                      ...m,
                      status: 'error',
                      errorDetail: err.message,
                    }
                  }),
                }
              })
            )
          },
          onComplete: () => {
            flushPendingChunks()
            setIsGenerating(false)
            abortCurrentStream.current = null
            setConversations((prev) =>
              prev.map((conv) => {
                if (conv.id !== targetConvId) return conv
                return {
                  ...conv,
                  messages: conv.messages.map((m) => {
                    if (m.id !== assistantMessageId) return m
                    return {
                      ...m,
                      status: 'complete',
                    }
                  }),
                }
              })
            )
          },
        }
      )

      abortCurrentStream.current = cancelFn
    },
    [activeConversationId, isGenerating, activeConversation, provider, queueChunk, flushPendingChunks]
  )

  const regenerateLastMessage = useCallback(() => {
    if (!activeConversation || isGenerating) return
    const msgs = activeConversation.messages
    if (msgs.length === 0) return

    // Find the latest user message index
    let lastUserIndex = -1
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i]?.role === 'user') {
        lastUserIndex = i
        break
      }
    }
    if (lastUserIndex === -1) return

    const lastUserMsg = msgs[lastUserIndex]
    if (!lastUserMsg) return

    // Prior history strictly preceding the latest user prompt
    const priorHistory = msgs.slice(0, lastUserIndex)

    const timestamp = Date.now()
    const assistantMessageId = `msg-a-${timestamp}`
    const timeStr = formatCurrentTime()

    const newAssistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      createdAt: timeStr,
      status: 'generating',
    }

    // Preserve all messages up to the user message being regenerated, then append the new assistant message
    const baseMsgs = msgs.slice(0, lastUserIndex + 1)

    setConversations((prev) =>
      prev.map((conv) => {
        if (conv.id !== activeConversation.id) return conv
        return {
          ...conv,
          updatedAt: new Date().toISOString(),
          messages: [...baseMsgs, newAssistantMessage],
        }
      })
    )

    setIsGenerating(true)
    const targetConvId = activeConversation.id

    const cancelFn = provider.streamResponse(
      lastUserMsg.content,
      priorHistory,
      {
        onChunk: (chunk: string) => {
          queueChunk(assistantMessageId, chunk)
        },
        onError: (err: Error) => {
          flushPendingChunks()
          setIsGenerating(false)
          abortCurrentStream.current = null
          setConversations((prev) =>
            prev.map((conv) => {
              if (conv.id !== targetConvId) return conv
              return {
                ...conv,
                messages: conv.messages.map((m) => {
                  if (m.id !== assistantMessageId) return m
                  return { ...m, status: 'error', errorDetail: err.message }
                }),
              }
            })
          )
        },
        onComplete: () => {
          flushPendingChunks()
          setIsGenerating(false)
          abortCurrentStream.current = null
          setConversations((prev) =>
            prev.map((conv) => {
              if (conv.id !== targetConvId) return conv
              return {
                ...conv,
                messages: conv.messages.map((m) => {
                  if (m.id !== assistantMessageId) return m
                  return { ...m, status: 'complete' }
                }),
              }
            })
          )
        },
      }
    )

    abortCurrentStream.current = cancelFn
  }, [activeConversation, isGenerating, provider, queueChunk, flushPendingChunks])

  return {
    conversations,
    activeConversationId,
    activeConversation,
    messages,
    isGenerating,
    createConversation,
    selectConversation,
    sendMessage,
    stopGeneration,
    regenerateLastMessage,
  }
}
