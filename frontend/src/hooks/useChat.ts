import { useState, useRef, useCallback, useEffect } from 'react'
import type {
  AppSettings,
  Attachment,
  Conversation,
  Message,
  ChatResponseProvider,
  PersistedAppState,
} from '@/types'
import { MOCK_CONVERSATIONS } from '@/data/mockData'
import { BackendResponseProvider } from '@/services/backendResponseService'
import {
  APP_STATE_STORAGE_VERSION,
  hasStoredAppState,
  loadAppState,
  saveAppState,
} from '@/services/storage'

const defaultProvider = new BackendResponseProvider()

interface ChatState {
  conversations: Conversation[]
  activeConversationId: string | null
  settings: AppSettings
}

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

function resolveConversationId(
  conversations: Conversation[],
  conversationId: string | null
): string | null {
  if (!conversationId) return null
  return conversations.some((conversation) => conversation.id === conversationId)
    ? conversationId
    : null
}

function getConversationSortTime(conversation: Conversation): number {
  const timestamp = Date.parse(conversation.updatedAt || conversation.createdAt)
  return Number.isNaN(timestamp) ? 0 : timestamp
}

function sortConversationsByUpdatedAt(conversations: Conversation[]): Conversation[] {
  return [...conversations].sort(
    (a, b) => getConversationSortTime(b) - getConversationSortTime(a)
  )
}

function getPersistableConversations(conversations: Conversation[]): Conversation[] {
  return sortConversationsByUpdatedAt(conversations).map((conversation) => ({
    ...conversation,
    messages: conversation.messages
      .filter((message) => message.status !== 'generating')
      .map((message) => {
        if (!message.attachments || message.attachments.length === 0) return message
        const validAttachments = message.attachments.filter((att) => att.status === 'uploaded')
        return {
          ...message,
          ...(validAttachments.length > 0
            ? { attachments: validAttachments }
            : { attachments: undefined }),
        }
      }),
  }))
}

function toPersistedAppState(state: ChatState): PersistedAppState {
  const conversations = getPersistableConversations(state.conversations)

  return {
    version: APP_STATE_STORAGE_VERSION,
    conversations,
    selectedConversationId: resolveConversationId(conversations, state.activeConversationId),
    settings: state.settings,
  }
}

function loadInitialChatState(): ChatState {
  const persistedState = loadAppState()

  if (!hasStoredAppState()) {
    return {
      conversations: MOCK_CONVERSATIONS,
      activeConversationId: null,
      settings: persistedState.settings,
    }
  }

  const conversations = sortConversationsByUpdatedAt(persistedState.conversations)

  return {
    conversations,
    activeConversationId: resolveConversationId(
      conversations,
      persistedState.selectedConversationId
    ),
    settings: persistedState.settings,
  }
}

export function useChat(provider: ChatResponseProvider = defaultProvider) {
  const [chatState, setChatState] = useState<ChatState>(loadInitialChatState)
  const [isGenerating, setIsGenerating] = useState(false)
  const chatStateRef = useRef(chatState)

  // Track active stream abort controller
  const abortCurrentStream = useRef<(() => void) | null>(null)
  const activeStreamConversationId = useRef<string | null>(null)

  // Streaming chunk batch buffer (frame-aligned via requestAnimationFrame)
  const pendingChunksRef = useRef<Map<string, string>>(new Map())
  const rafIdRef = useRef<number | null>(null)

  const commitChatState = useCallback(
    (nextState: ChatState, options: { persist: boolean }): ChatState => {
      const conversations = sortConversationsByUpdatedAt(nextState.conversations)
      const normalizedState: ChatState = {
        ...nextState,
        conversations,
        activeConversationId: resolveConversationId(conversations, nextState.activeConversationId),
      }

      chatStateRef.current = normalizedState
      setChatState(normalizedState)

      if (options.persist) {
        saveAppState(toPersistedAppState(normalizedState))
      }

      return normalizedState
    },
    []
  )

  // Flush pending streaming chunk buffer into React state
  const flushPendingChunks = useCallback((): ChatState => {
    if (rafIdRef.current !== null && typeof window !== 'undefined') {
      window.cancelAnimationFrame(rafIdRef.current)
      rafIdRef.current = null
    }
    if (pendingChunksRef.current.size === 0) return chatStateRef.current

    const chunkEntries = Array.from(pendingChunksRef.current.entries())
    pendingChunksRef.current.clear()

    const chunkMap = new Map(chunkEntries)
    const currentState = chatStateRef.current
    let stateUpdated = false

    const conversations = currentState.conversations.map((conv) => {
      let convUpdated = false
      const updatedMessages = conv.messages.map((m) => {
        const chunkToAdd = chunkMap.get(m.id)
        if (chunkToAdd) {
          convUpdated = true
          return { ...m, content: m.content + chunkToAdd }
        }
        return m
      })
      if (!convUpdated) return conv
      stateUpdated = true
      return { ...conv, messages: updatedMessages }
    })

    if (!stateUpdated) return currentState

    return commitChatState(
      {
        ...currentState,
        conversations,
      },
      { persist: false }
    )
  }, [commitChatState])

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
  const conversations = chatState.conversations
  const activeConversationId = chatState.activeConversationId
  const activeConversation = conversations.find((c) => c.id === activeConversationId)
  const messages = activeConversation ? activeConversation.messages : []

  // Abort active stream and clean up state across all conversations
  const abortActiveGeneration = useCallback((nextActiveConversationId?: string | null) => {
    const abortTimestamp = new Date().toISOString()

    if (abortCurrentStream.current) {
      abortCurrentStream.current()
      abortCurrentStream.current = null
      activeStreamConversationId.current = null
    }
    const flushedState = flushPendingChunks()
    setIsGenerating(false)

    // Mark any currently generating message as complete across conversations to preserve partial content
    const conversations = flushedState.conversations.map((conv) => {
      const hasGenerating = conv.messages.some((m) => m.status === 'generating')
      if (!hasGenerating) return conv
      return {
        ...conv,
        updatedAt: abortTimestamp,
        messages: conv.messages.map((m) => {
          if (m.status === 'generating') {
            return { ...m, status: 'complete' as const }
          }
          return m
        }),
      }
    })

    commitChatState(
      {
        ...flushedState,
        conversations,
        activeConversationId:
          nextActiveConversationId === undefined
            ? flushedState.activeConversationId
            : nextActiveConversationId,
      },
      { persist: true }
    )
  }, [commitChatState, flushPendingChunks])

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
    abortActiveGeneration(null)
  }, [abortActiveGeneration])

  const selectConversation = useCallback(
    (id: string) => {
      abortActiveGeneration(id)
    },
    [abortActiveGeneration]
  )

  const deleteConversation = useCallback(
    (id: string) => {
      const currentState = chatStateRef.current
      const shouldAbortActiveStream =
        activeStreamConversationId.current === id ||
        (currentState.activeConversationId === id && abortCurrentStream.current !== null)

      let baseState = currentState

      if (shouldAbortActiveStream) {
        abortCurrentStream.current?.()
        abortCurrentStream.current = null
        activeStreamConversationId.current = null
        baseState = flushPendingChunks()
        setIsGenerating(false)
      }

      const conversations = baseState.conversations.filter(
        (conversation) => conversation.id !== id
      )
      const activeConversationId =
        baseState.activeConversationId === id
          ? conversations[0]?.id ?? null
          : baseState.activeConversationId

      commitChatState(
        {
          ...baseState,
          conversations,
          activeConversationId,
        },
        { persist: true }
      )
    },
    [commitChatState, flushPendingChunks]
  )

  const sendMessage = useCallback(
    (content: string, attachments?: Attachment[]) => {
      const trimmed = content.trim()
      const hasAttachments = Boolean(attachments && attachments.length > 0)
      if ((!trimmed && !hasAttachments) || isGenerating) return

      const promptText = trimmed || (hasAttachments ? `[Attached: ${attachments!.map((a) => a.name).join(', ')}]` : '')
      const timeStr = formatCurrentTime()
      const timestamp = Date.now()
      const nowISO = new Date(timestamp).toISOString()
      const userMessageId = `msg-u-${timestamp}`
      const assistantMessageId = `msg-a-${timestamp}`

      const newUserMessage: Message = {
        id: userMessageId,
        role: 'user',
        content: trimmed || (hasAttachments ? `Attached: ${attachments!.map((a) => a.name).join(', ')}` : ''),
        timestamp: nowISO,
        createdAt: timeStr,
        status: 'complete',
        ...(hasAttachments ? { attachments } : {}),
      }

      const initialAssistantMessage: Message = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        timestamp: nowISO,
        createdAt: timeStr,
        status: 'generating',
      }

      const currentState = chatStateRef.current
      const activeConversation = currentState.conversations.find(
        (conversation) => conversation.id === currentState.activeConversationId
      )
      let currentConvId = currentState.activeConversationId
      const currentHistory = activeConversation ? activeConversation.messages : []

      if (!currentConvId) {
        // Create new conversation
        currentConvId = `conv-${timestamp}`
        const derivedTitle = deriveTitleFromPrompt(trimmed || (hasAttachments ? attachments![0]?.name || 'File' : 'New Thread'))

        const newConversation: Conversation = {
          id: currentConvId,
          title: derivedTitle,
          createdAt: nowISO,
          updatedAt: nowISO,
          messages: [newUserMessage, initialAssistantMessage],
        }

        commitChatState(
          {
            ...currentState,
            conversations: [newConversation, ...currentState.conversations],
            activeConversationId: currentConvId,
          },
          { persist: true }
        )
      } else {
        // Append to existing active conversation
        const conversations = currentState.conversations.map((conv) => {
          if (conv.id !== currentConvId) return conv
          return {
            ...conv,
            updatedAt: nowISO,
            messages: [...conv.messages, newUserMessage, initialAssistantMessage],
          }
        })

        commitChatState(
          {
            ...currentState,
            conversations,
          },
          { persist: true }
        )
      }

      setIsGenerating(true)

      const targetConvId = currentConvId
      activeStreamConversationId.current = targetConvId

      const cancelFn = provider.streamResponse(
        promptText,
        currentHistory,
        {
          onChunk: (chunk: string) => {
            queueChunk(assistantMessageId, chunk)
          },
          onError: (err: Error) => {
            const flushedState = flushPendingChunks()
            setIsGenerating(false)
            abortCurrentStream.current = null
            if (activeStreamConversationId.current === targetConvId) {
              activeStreamConversationId.current = null
            }
            const completedAt = new Date().toISOString()
            const conversations = flushedState.conversations.map((conv) => {
              if (conv.id !== targetConvId) return conv
              return {
                ...conv,
                updatedAt: completedAt,
                messages: conv.messages.map((m) => {
                  if (m.id !== assistantMessageId) return m
                  return {
                    ...m,
                    status: 'error' as const,
                    errorDetail: err.message,
                  }
                }),
              }
            })

            commitChatState(
              {
                ...flushedState,
                conversations,
              },
              { persist: true }
            )
          },
          onComplete: () => {
            const flushedState = flushPendingChunks()
            setIsGenerating(false)
            abortCurrentStream.current = null
            if (activeStreamConversationId.current === targetConvId) {
              activeStreamConversationId.current = null
            }
            const completedAt = new Date().toISOString()
            const conversations = flushedState.conversations.map((conv) => {
              if (conv.id !== targetConvId) return conv
              return {
                ...conv,
                updatedAt: completedAt,
                messages: conv.messages.map((m) => {
                  if (m.id !== assistantMessageId) return m
                  return {
                    ...m,
                    status: 'complete' as const,
                  }
                }),
              }
            })

            commitChatState(
              {
                ...flushedState,
                conversations,
              },
              { persist: true }
            )
          },
        }
      )

      abortCurrentStream.current = cancelFn
    },
    [commitChatState, flushPendingChunks, isGenerating, provider, queueChunk]
  )

  const regenerateLastMessage = useCallback(() => {
    const currentState = chatStateRef.current
    const activeConversation = currentState.conversations.find(
      (conversation) => conversation.id === currentState.activeConversationId
    )
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
    const nowISO = new Date(timestamp).toISOString()
    const assistantMessageId = `msg-a-${timestamp}`
    const timeStr = formatCurrentTime()

    const newAssistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: nowISO,
      createdAt: timeStr,
      status: 'generating',
    }

    // Preserve all messages up to the user message being regenerated, then append the new assistant message
    const baseMsgs = msgs.slice(0, lastUserIndex + 1)

    const conversations = currentState.conversations.map((conv) => {
      if (conv.id !== activeConversation.id) return conv
      return {
        ...conv,
        updatedAt: nowISO,
        messages: [...baseMsgs, newAssistantMessage],
      }
    })

    commitChatState(
      {
        ...currentState,
        conversations,
      },
      { persist: true }
    )

    setIsGenerating(true)
    const targetConvId = activeConversation.id
    activeStreamConversationId.current = targetConvId

    const cancelFn = provider.streamResponse(
      lastUserMsg.content,
      priorHistory,
      {
        onChunk: (chunk: string) => {
          queueChunk(assistantMessageId, chunk)
        },
        onError: (err: Error) => {
          const flushedState = flushPendingChunks()
          setIsGenerating(false)
          abortCurrentStream.current = null
          if (activeStreamConversationId.current === targetConvId) {
            activeStreamConversationId.current = null
          }
          const completedAt = new Date().toISOString()
          const conversations = flushedState.conversations.map((conv) => {
            if (conv.id !== targetConvId) return conv
            return {
              ...conv,
              updatedAt: completedAt,
              messages: conv.messages.map((m) => {
                if (m.id !== assistantMessageId) return m
                return { ...m, status: 'error' as const, errorDetail: err.message }
              }),
            }
          })

          commitChatState(
            {
              ...flushedState,
              conversations,
            },
            { persist: true }
          )
        },
        onComplete: () => {
          const flushedState = flushPendingChunks()
          setIsGenerating(false)
          abortCurrentStream.current = null
          if (activeStreamConversationId.current === targetConvId) {
            activeStreamConversationId.current = null
          }
          const completedAt = new Date().toISOString()
          const conversations = flushedState.conversations.map((conv) => {
            if (conv.id !== targetConvId) return conv
            return {
              ...conv,
              updatedAt: completedAt,
              messages: conv.messages.map((m) => {
                if (m.id !== assistantMessageId) return m
                return { ...m, status: 'complete' as const }
              }),
            }
          })

          commitChatState(
            {
              ...flushedState,
              conversations,
            },
            { persist: true }
          )
        },
      }
    )

    abortCurrentStream.current = cancelFn
  }, [commitChatState, flushPendingChunks, isGenerating, provider, queueChunk])

  return {
    conversations,
    activeConversationId,
    activeConversation,
    messages,
    isGenerating,
    createConversation,
    selectConversation,
    deleteConversation,
    sendMessage,
    stopGeneration,
    regenerateLastMessage,
  }
}
