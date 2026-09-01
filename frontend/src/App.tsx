import React, { useState, useEffect } from 'react'
import { AppShell } from '@/layouts/AppShell'
import { Sidebar } from '@/components/sidebar/Sidebar'
import { WorkspaceHeader } from '@/components/workspace/WorkspaceHeader'
import { WelcomeView } from '@/components/workspace/WelcomeView'
import { MessageList } from '@/components/workspace/MessageList'
import { Composer } from '@/components/workspace/Composer'
import { useChat } from '@/hooks/useChat'
import {
  PROMPT_STARTERS,
  INITIAL_MODEL_STATUS,
} from '@/data/mockData'
import type { ModelStatus, Attachment } from '@/types'

export const App: React.FC = () => {
  const [modelStatus, setModelStatus] = useState<ModelStatus>(INITIAL_MODEL_STATUS)
  const [composerText, setComposerText] = useState<string>('')

  const {
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
  } = useChat()

  // Fetch real model runtime status from backend on mount
  useEffect(() => {
    fetch('/api/model')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) {
          setModelStatus({
            name: data.name || 'Gemma 4 E4B',
            architecture: data.architecture || '4B Parameters',
            runtime: data.runtime || 'local',
            status: data.status === 'ready' ? 'ready' : data.status === 'offline' ? 'offline' : 'loading',
          })
        }
      })
      .catch(() => {
        setModelStatus((prev) => ({ ...prev, status: 'offline' }))
      })
  }, [])

  // Global keyboard shortcut: Ctrl+N (Windows/Linux) or Cmd+N (macOS) for New Thread
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'n' || e.key === 'N')) {
        e.preventDefault()
        createConversation()
        setComposerText('')
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [createConversation])

  const currentTitle = activeConversation ? activeConversation.title : 'New Thread'

  const handleSelectStarter = (prompt: string) => {
    setComposerText(prompt)
  }

  const handleSend = (attachments?: Attachment[]) => {
    const textToSend = composerText
    const hasAttachments = Boolean(attachments && attachments.length > 0)
    if ((!textToSend.trim() && !hasAttachments) || isGenerating) return
    setComposerText('')
    sendMessage(textToSend, attachments)
  }

  return (
    <AppShell
      sidebar={({ onCloseMobile }) => (
        <Sidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          modelStatus={modelStatus}
          onSelectConversation={selectConversation}
          onDeleteConversation={deleteConversation}
          onNewConversation={() => {
            createConversation()
            setComposerText('')
          }}
          onCloseMobile={onCloseMobile}
        />
      )}
    >
      {({ onToggleSidebar }) => (
        <main className="flex flex-col h-full w-full overflow-hidden bg-surface-0">
          {/* Header */}
          <WorkspaceHeader
            title={currentTitle}
            modelStatus={modelStatus}
            onToggleSidebar={onToggleSidebar}
          />

          {/* Central Workspace Content Area */}
          <div className="flex-1 overflow-hidden flex flex-col justify-between">
            {messages.length === 0 ? (
              <div className="flex-1 overflow-y-auto flex flex-col justify-center">
                <WelcomeView
                  starters={PROMPT_STARTERS}
                  modelStatus={modelStatus}
                  onSelectStarter={handleSelectStarter}
                />
              </div>
            ) : (
              <MessageList
                messages={messages}
                isGenerating={isGenerating}
                onRegenerate={regenerateLastMessage}
              />
            )}
          </div>

          {/* Composer */}
          <Composer
            key={activeConversationId || 'new'}
            value={composerText}
            onChange={setComposerText}
            onSend={handleSend}
            onStop={stopGeneration}
            isGenerating={isGenerating}
            disabled={isGenerating}
          />
        </main>
      )}
    </AppShell>
  )
}

export default App
