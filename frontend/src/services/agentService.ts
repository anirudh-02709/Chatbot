import type { AgentRunResponse, GenerationMode } from '@/types'

export interface RunAgentOptions {
  message: string
  mode?: GenerationMode
  max_iterations?: number
  conversation_id?: string
  attachment_ids?: string[]
}

export async function runAgent(
  options: RunAgentOptions,
  signal?: AbortSignal
): Promise<AgentRunResponse> {
  const response = await fetch('/api/agent/run', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(options),
    signal,
  })

  if (!response.ok) {
    let errorDetail = `Agent request failed (${response.status})`
    try {
      const errJson = await response.json()
      if (errJson.detail) {
        errorDetail =
          typeof errJson.detail === 'string'
            ? errJson.detail
            : JSON.stringify(errJson.detail)
      }
    } catch {
      // Ignore JSON decode error
    }
    throw new Error(errorDetail)
  }

  return response.json()
}
