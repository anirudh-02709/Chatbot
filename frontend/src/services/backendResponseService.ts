import type { ChatResponseProvider, Message } from '@/types'

export class BackendResponseProvider implements ChatResponseProvider {
  streamResponse(
    prompt: string,
    history: Message[],
    callbacks: {
      onChunk: (chunk: string) => void
      onError: (error: Error) => void
      onComplete: () => void
    }
  ): () => void {
    const abortController = new AbortController()

    // Map conversation history to clean role and content (strictly content, never thinking or UI metadata)
    const messages = history
      .filter((m) => m.status !== 'error' && m.content.trim().length > 0)
      .map((m) => ({
        role: m.role,
        content: m.content,
      }))
      .concat({
        role: 'user',
        content: prompt,
      })

    fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ messages }),
      signal: abortController.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          let errorText = `Backend error (${response.status})`
          try {
            const errJson = await response.json()
            if (errJson.detail) {
              errorText = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail)
            }
          } catch {
            // Ignore JSON decode error
          }
          callbacks.onError(new Error(errorText))
          return
        }

        const reader = response.body?.getReader()
        if (!reader) {
          callbacks.onError(new Error('Failed to initialize response stream from backend.'))
          return
        }

        const decoder = new TextDecoder()
        let buffer = ''
        let currentEvent = 'message'

        try {
          while (true) {
            const { done, value } = await reader.read()
            if (done) break

            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop() || ''

            for (const line of lines) {
              const trimmed = line.trim()
              if (!trimmed) {
                currentEvent = 'message'
                continue
              }

              if (trimmed.startsWith('event:')) {
                currentEvent = trimmed.slice(6).trim()
              } else if (trimmed.startsWith('data:')) {
                const dataStr = trimmed.slice(5).trim()
                try {
                  const data = JSON.parse(dataStr)
                  if (currentEvent === 'content' && data.chunk) {
                    callbacks.onChunk(data.chunk)
                  } else if (currentEvent === 'error' && data.message) {
                    callbacks.onError(new Error(data.message))
                    return
                  } else if (currentEvent === 'complete') {
                    callbacks.onComplete()
                    return
                  }
                } catch {
                  // Ignore JSON parse errors for non-JSON frames
                }
              }
            }
          }
          callbacks.onComplete()
        } catch (streamErr: unknown) {
          if (streamErr instanceof DOMException && streamErr.name === 'AbortError') {
            return
          }
          callbacks.onError(
            streamErr instanceof Error ? streamErr : new Error(String(streamErr))
          )
        }
      })
      .catch((fetchErr: unknown) => {
        if (fetchErr instanceof DOMException && fetchErr.name === 'AbortError') {
          return
        }
        callbacks.onError(
          fetchErr instanceof Error
            ? fetchErr
            : new Error('Network error: Unable to communicate with the local backend.')
        )
      })

    return () => {
      abortController.abort()
    }
  }
}
