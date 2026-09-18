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

export type AppMode = 'chat' | 'agent'

export interface AgentToolCallSummary {
  tool_name: string
  status: string
  success: boolean
  duration_ms?: number
  error_type?: string
  arguments?: Record<string, unknown>
}

export interface AgentActivity {
  status: string
  termination_reason?: string
  iteration_count: number
  total_duration_ms?: number
  tool_calls: AgentToolCallSummary[]
}

export interface AgentRunResponse {
  answer: string
  status: string
  termination_reason?: string
  iteration_count: number
  total_duration_ms?: number
  tool_calls: AgentToolCallSummary[]
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
  agentActivity?: AgentActivity
  appMode?: AppMode
}

export interface Conversation {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messages: Message[]
}

export type GenerationMode = 'local_gemma' | 'omniroute'

export interface AppSettings {
  generationMode?: GenerationMode
  appMode?: AppMode
  [key: string]: unknown
}

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
  runtime: 'local' | 'remote' | 'omniroute'
  status: 'ready' | 'loading' | 'offline'
  mode?: GenerationMode
}

export interface ChatResponseProvider {
  streamResponse: (
    prompt: string,
    history: Message[],
    callbacks: {
      onChunk: (chunk: string) => void
      onError: (error: Error) => void
      onComplete: () => void
    },
    mode?: GenerationMode
  ) => () => void // Returns abort/cancel function
}
