export type MessageRole = 'user' | 'assistant'

export type MessageStatus = 'generating' | 'complete' | 'error'

export interface Message {
  id: string
  role: MessageRole
  content: string
  createdAt: string
  status: MessageStatus
  errorDetail?: string
}

export interface Conversation {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messages: Message[]
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
