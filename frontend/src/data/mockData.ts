import type { Conversation, PromptStarter, ModelStatus } from '@/types'

export const INITIAL_MODEL_STATUS: ModelStatus = {
  name: 'Gemma 4 E4B',
  architecture: '4B Parameters',
  runtime: 'local',
  status: 'ready',
}

export const MOCK_CONVERSATIONS: Conversation[] = [
  {
    id: 'conv-1',
    title: 'Distributed lock patterns in Go',
    createdAt: '2026-08-31T10:40:00Z',
    updatedAt: '2026-08-31T10:42:00Z',
    messages: [
      {
        id: 'm1-1',
        role: 'user',
        content: 'What are the main patterns for implementing distributed locks in Go, and how do Redis Redlock vs etcd compare?',
        createdAt: '10:40 AM',
        status: 'complete',
      },
      {
        id: 'm1-2',
        role: 'assistant',
        content: `When implementing distributed locks in Go, the two most common backends are **Redis** (often using the Redlock algorithm) and **etcd** (using raft consensus leases).

### 1. etcd (Consensus-based)
etcd uses the Raft algorithm, providing strict linearizability:
- **Mechanism**: Creates a key tied to a lease with a TTL and auto-keepalive.
- **Pros**: Strong consistency guarantees, no split-brain risks under network partitions.
- **Cons**: Slightly higher write latency due to quorum consensus.

### 2. Redis (Redlock algorithm)
- **Mechanism**: Acquires locks across $N$ independent Redis instances sequentially with a short timeout.
- **Pros**: High throughput and sub-millisecond acquisition latency.
- **Cons**: Relies on synchronized wall-clock time and can be prone to timing edge cases during GC pauses.

\`\`\`go
// Example etcd concurrency session in Go
cli, _ := clientv3.New(clientv3.Config{Endpoints: []string{"localhost:2379"}})
defer cli.Close()

s, _ := concurrency.NewSession(cli, concurrency.WithTTL(5))
defer s.Close()

m := concurrency.NewMutex(s, "/distributed-lock-key")
if err := m.Lock(context.Background()); err != nil {
    log.Fatal(err)
}
// Critical section...
m.Unlock(context.Background())
\`\`\`

**Recommendation**: Use **etcd** when safety and correctness are paramount; use **Redis** when high throughput is needed and intermittent lock loss under partition is tolerable.`,
        createdAt: '10:42 AM',
        status: 'complete',
      },
    ],
  },
  {
    id: 'conv-2',
    title: 'Tailwind v4 theme architecture',
    createdAt: '2026-08-31T09:12:00Z',
    updatedAt: '2026-08-31T09:15:00Z',
    messages: [
      {
        id: 'm2-1',
        role: 'user',
        content: 'How does theme token customization work in Tailwind CSS v4 without a tailwind.config.js file?',
        createdAt: '09:12 AM',
        status: 'complete',
      },
      {
        id: 'm2-2',
        role: 'assistant',
        content: `In Tailwind CSS v4, the configuration has transitioned to a **CSS-first architecture**. Instead of \`tailwind.config.js\`, you configure tokens directly inside your CSS using the \`@theme\` directive:

\`\`\`css
@import "tailwindcss";

@theme {
  --color-surface-0: #0b0e14;
  --color-surface-1: #11151c;
  --color-accent-base: #2563eb;
  --font-sans: system-ui, -apple-system, sans-serif;
}
\`\`\`

Any \`--color-*\` token defined in \`@theme\` automatically generates utilities like \`bg-surface-0\`, \`text-accent-base\`, and \`border-surface-1\`.`,
        createdAt: '09:15 AM',
        status: 'complete',
      },
    ],
  },
  {
    id: 'conv-3',
    title: 'TypeScript 5.7 satisfies operator',
    createdAt: '2026-08-30T16:00:00Z',
    updatedAt: '2026-08-30T16:05:00Z',
    messages: [
      {
        id: 'm3-1',
        role: 'user',
        content: 'Can you demonstrate the difference between type annotations and the satisfies operator in TypeScript?',
        createdAt: 'Yesterday',
        status: 'complete',
      },
      {
        id: 'm3-2',
        role: 'assistant',
        content: `The \`satisfies\` operator validates that an expression matches a type **without widening or changing the inferred type** of the expression.

\`\`\`typescript
type Color = string | { r: number; g: number; b: number };

// Using type annotation: palette.primary is widened to Color (string | object)
const paletteA: Record<string, Color> = {
  primary: '#2563eb',
};
// paletteA.primary.toUpperCase() -> Error: Property does not exist on type object

// Using satisfies: palette.primary is validated against Color but keeps string type
const paletteB = {
  primary: '#2563eb',
} satisfies Record<string, Color>;

// paletteB.primary.toUpperCase() -> Valid string method!
\`\`\``,
        createdAt: 'Yesterday',
        status: 'complete',
      },
    ],
  },
]

export const PROMPT_STARTERS: PromptStarter[] = [
  {
    id: 'starter-1',
    title: 'Code Analysis',
    description: 'Review architecture, identify edge cases, or optimize algorithmic complexity',
    prompt: 'Can you analyze this code snippet for potential race conditions and performance bottlenecks?',
    category: 'Engineering',
  },
  {
    id: 'starter-2',
    title: 'System Design',
    description: 'Draft scalable data models, caching layers, and API service boundaries',
    prompt: 'I want to design a real-time event streaming pipeline. What are the key architectural trade-offs between push vs pull streaming?',
    category: 'Architecture',
  },
  {
    id: 'starter-3',
    title: 'Technical Writing',
    description: 'Synthesize complex engineering concepts into concise specifications or RFCs',
    prompt: 'Draft an engineering RFC outline for migrating service communication from REST to gRPC.',
    category: 'Documentation',
  },
  {
    id: 'starter-4',
    title: 'Data Extraction',
    description: 'Parse, transform, or structure unstructured technical logs and schemas',
    prompt: 'Help me write a parsing routine to extract structured key-value metrics from server log outputs.',
    category: 'Data',
  },
]
