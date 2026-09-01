export type MessageRole = 'user' | 'assistant'

export type MessageStatus = 'generating' | 'complete' | 'error'

export type AttachmentStatus = 'pending' | 'uploading' | 'uploaded' | 'error'

export interface Attachment {
  id: string
  name: string
  size: number
  mimeType: string
  status: AttachmentStatus
  uploadedAt?: string
  errorDetail?: string
  progress?: number
}

export interface Message {
  id: string
  role: MessageRole
  content: string
  timestamp: string
  createdAt: string
  status: MessageStatus
  errorDetail?: string
  attachments?: Attachment[]
}

export interface Conversation {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messages: Message[]
}

export type AppSettings = Record<string, unknown>

export interface PersistedAppState {
  version: 1
  conversations: Conversation[]
  selectedConversationId: string | null
  settings: AppSettings
}

export interface PromptStarter {
  id: string
  title: string
  description: string
  prompt: string
  category: string
}

export interface ModelStatus {
  name: string
  architecture: string
  runtime: 'local' | 'remote'
  status: 'ready' | 'loading' | 'offline'
}

export interface ChatResponseProvider {
  streamResponse: (
    prompt: string,
    history: Message[],
    callbacks: {
      onChunk: (chunk: string) => void
      onError: (error: Error) => void
      onComplete: () => void
    }
  ) => () => void // Returns abort/cancel function
}
