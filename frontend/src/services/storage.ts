import type {
  AppMode,
  AgentActivity,
  AgentToolCallSummary,
  AppSettings,
  Attachment,
  AttachmentStatus,
  Conversation,
  Message,
  MessageRole,
  MessageStatus,
  PersistedAppState,
} from '@/types'

export const APP_STATE_STORAGE_KEY = 'ai-assistant-state'
export const APP_STATE_STORAGE_VERSION = 1

const DEFAULT_SETTINGS: AppSettings = {
  generationMode: 'omniroute',
  appMode: 'chat',
}

function createDefaultAppState(): PersistedAppState {
  return {
    version: APP_STATE_STORAGE_VERSION,
    conversations: [],
    selectedConversationId: null,
    settings: DEFAULT_SETTINGS,
  }
}

function getStorage(): Storage | null {
  if (typeof window === 'undefined') return null

  try {
    return window.localStorage
  } catch {
    return null
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function asString(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}

function isMessageRole(value: unknown): value is MessageRole {
  return value === 'user' || value === 'assistant'
}

function isMessageStatus(value: unknown): value is MessageStatus {
  return value === 'generating' || value === 'complete' || value === 'error'
}

function normalizeAttachment(value: unknown): Attachment | null {
  if (!isRecord(value)) return null

  const id = asString(value.id)
  const name = asString(value.name)
  const size = typeof value.size === 'number' && Number.isFinite(value.size) ? value.size : null
  const mimeType = asString(value.mimeType) ?? 'application/octet-stream'

  if (!id || !name || size === null) return null

  let status: AttachmentStatus
  let errorDetail = asString(value.errorDetail)

  if (value.status === 'uploaded') {
    status = 'uploaded'
  } else if (value.status === 'error') {
    status = 'error'
  } else if (value.status === 'uploading' || value.status === 'pending') {
    status = 'error'
    errorDetail = errorDetail ?? 'Upload was interrupted'
  } else {
    status = 'error'
    errorDetail = errorDetail ?? 'Invalid attachment state'
  }

  const uploadedAt = asString(value.uploadedAt)

  return {
    id,
    name,
    size,
    mimeType,
    status,
    ...(uploadedAt ? { uploadedAt } : {}),
    ...(errorDetail ? { errorDetail } : {}),
  }
}

function normalizeAgentToolCall(value: unknown): AgentToolCallSummary | null {
  if (!isRecord(value)) return null
  const toolName = asString(value.tool_name)
  if (!toolName) return null
  return {
    tool_name: toolName,
    status: asString(value.status) ?? 'completed',
    success: typeof value.success === 'boolean' ? value.success : true,
    duration_ms: typeof value.duration_ms === 'number' ? value.duration_ms : undefined,
    error_type: asString(value.error_type) ?? undefined,
    arguments: isRecord(value.arguments) ? (value.arguments as Record<string, unknown>) : undefined,
  }
}

function normalizeAgentActivity(value: unknown): AgentActivity | null {
  if (!isRecord(value)) return null
  const status = asString(value.status) ?? 'completed'
  const terminationReason = asString(value.termination_reason) ?? undefined
  const iterationCount = typeof value.iteration_count === 'number' ? value.iteration_count : 1
  const totalDurationMs = typeof value.total_duration_ms === 'number' ? value.total_duration_ms : undefined
  const rawToolCalls = Array.isArray(value.tool_calls) ? value.tool_calls : []
  const toolCalls = rawToolCalls
    .map(normalizeAgentToolCall)
    .filter((tc): tc is AgentToolCallSummary => tc !== null)

  return {
    status,
    termination_reason: terminationReason,
    iteration_count: iterationCount,
    total_duration_ms: totalDurationMs,
    tool_calls: toolCalls,
  }
}

function normalizeMessage(value: unknown): Message | null {
  if (!isRecord(value)) return null

  const id = asString(value.id)
  const role = value.role
  const content = asString(value.content)

  if (!id || !isMessageRole(role) || content === null) return null

  const timestamp = asString(value.timestamp) ?? asString(value.createdAt) ?? ''
  const createdAt = asString(value.createdAt) ?? timestamp
  const status = isMessageStatus(value.status) ? value.status : 'complete'
  const errorDetail = asString(value.errorDetail)

  const rawAttachments = Array.isArray(value.attachments) ? value.attachments : []
  const attachments = rawAttachments
    .map(normalizeAttachment)
    .filter((att): att is Attachment => att !== null)

  const agentActivity = isRecord(value.agentActivity)
    ? normalizeAgentActivity(value.agentActivity)
    : undefined
  const appMode: AppMode | undefined =
    value.appMode === 'agent' || value.appMode === 'chat'
      ? value.appMode
      : undefined

  return {
    id,
    role,
    content,
    timestamp,
    createdAt,
    status,
    ...(errorDetail ? { errorDetail } : {}),
    ...(attachments.length > 0 ? { attachments } : {}),
    ...(agentActivity ? { agentActivity } : {}),
    ...(appMode ? { appMode } : {}),
  }
}

function normalizeConversation(value: unknown): Conversation | null {
  if (!isRecord(value)) return null

  const id = asString(value.id)
  if (!id) return null

  const createdAt = asString(value.createdAt) ?? new Date().toISOString()
  const updatedAt = asString(value.updatedAt) ?? createdAt
  const rawMessages = Array.isArray(value.messages) ? value.messages : []

  return {
    id,
    title: asString(value.title) ?? 'Untitled Thread',
    createdAt,
    updatedAt,
    messages: rawMessages
      .map((message) => normalizeMessage(message))
      .filter((message): message is Message => message !== null),
  }
}

function normalizeSettings(value: unknown): AppSettings {
  if (!isRecord(value)) return DEFAULT_SETTINGS
  const mode = value.generationMode === 'local_gemma' || value.generationMode === 'omniroute'
    ? value.generationMode
    : 'omniroute'
  const appMode = value.appMode === 'agent' || value.appMode === 'chat'
    ? value.appMode
    : 'chat'
  return { ...value, generationMode: mode, appMode }
}

function normalizeAppState(value: unknown): PersistedAppState | null {
  if (!isRecord(value)) return null
  if (value.version !== APP_STATE_STORAGE_VERSION) return null

  const rawConversations = Array.isArray(value.conversations) ? value.conversations : []
  const conversations = rawConversations
    .map((conversation) => normalizeConversation(conversation))
    .filter((conversation): conversation is Conversation => conversation !== null)

  const selectedConversationId = asString(value.selectedConversationId)
  const hasSelectedConversation =
    selectedConversationId !== null &&
    conversations.some((conversation) => conversation.id === selectedConversationId)

  return {
    version: APP_STATE_STORAGE_VERSION,
    conversations,
    selectedConversationId: hasSelectedConversation ? selectedConversationId : null,
    settings: normalizeSettings(value.settings),
  }
}

export function loadAppState(): PersistedAppState {
  const storage = getStorage()
  if (!storage) return createDefaultAppState()

  try {
    const rawState = storage.getItem(APP_STATE_STORAGE_KEY)
    if (!rawState) return createDefaultAppState()

    const parsedState: unknown = JSON.parse(rawState)
    return normalizeAppState(parsedState) ?? createDefaultAppState()
  } catch {
    return createDefaultAppState()
  }
}

export function hasStoredAppState(): boolean {
  const storage = getStorage()
  if (!storage) return false

  try {
    return storage.getItem(APP_STATE_STORAGE_KEY) !== null
  } catch {
    return false
  }
}

export function saveAppState(state: PersistedAppState): boolean {
  const storage = getStorage()
  if (!storage) return false

  try {
    storage.setItem(APP_STATE_STORAGE_KEY, JSON.stringify(state))
    return true
  } catch {
    return false
  }
}

export function clearAppState(): boolean {
  const storage = getStorage()
  if (!storage) return false

  try {
    storage.removeItem(APP_STATE_STORAGE_KEY)
    return true
  } catch {
    return false
  }
}
