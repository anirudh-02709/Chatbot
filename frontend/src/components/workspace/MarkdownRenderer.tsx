import React, { useState, memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Copy, Check } from 'lucide-react'

interface MarkdownRendererProps {
  content: string
  className?: string
}

interface CodeBlockProps {
  language?: string
  children: string
}

const CodeBlock: React.FC<CodeBlockProps> = ({ language, children }) => {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(children)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard fallback
    }
  }

  return (
    <div className="my-3 rounded-lg border border-surface-border bg-surface-0 overflow-hidden shadow-xs">
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-surface-2/70 border-b border-surface-border text-[11px] font-mono text-text-muted">
        <span className="uppercase tracking-wider font-semibold text-text-dim">
          {language || 'code'}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] text-text-dim hover:text-text-primary hover:bg-surface-3 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-focus"
          title="Copy code snippet"
          aria-label="Copy code"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3 text-emerald-400" />
              <span className="text-emerald-400 font-medium">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="w-3 h-3" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto font-mono text-xs text-text-secondary leading-relaxed">
        <code>{children}</code>
      </pre>
    </div>
  )
}

function extractTextFromChildren(children: React.ReactNode): string {
  if (typeof children === 'string') return children
  if (typeof children === 'number') return String(children)
  if (Array.isArray(children)) {
    return children.map(extractTextFromChildren).join('')
  }
  if (React.isValidElement(children) && children.props && (children.props as { children?: React.ReactNode }).children) {
    return extractTextFromChildren((children.props as { children?: React.ReactNode }).children)
  }
  return ''
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = memo(({
  content,
  className = '',
}) => {
  if (!content) return null

  return (
    <div className={`markdown-content text-xs sm:text-sm text-text-secondary space-y-2.5 ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Headings
          h1: ({ node, children, ...props }) => (
            <h1 className="text-base sm:text-lg font-bold text-text-primary mt-4 mb-2 pb-1 border-b border-surface-border/60 first:mt-0" {...props}>
              {children}
            </h1>
          ),
          h2: ({ node, children, ...props }) => (
            <h2 className="text-sm sm:text-base font-bold text-text-primary mt-3.5 mb-1.5 first:mt-0" {...props}>
              {children}
            </h2>
          ),
          h3: ({ node, children, ...props }) => (
            <h3 className="text-xs sm:text-sm font-semibold text-text-primary mt-3 mb-1 first:mt-0" {...props}>
              {children}
            </h3>
          ),
          h4: ({ node, children, ...props }) => (
            <h4 className="text-xs font-semibold text-text-primary mt-2.5 mb-1 first:mt-0" {...props}>
              {children}
            </h4>
          ),
          h5: ({ node, children, ...props }) => (
            <h5 className="text-xs font-medium text-text-primary mt-2 mb-0.5 first:mt-0" {...props}>
              {children}
            </h5>
          ),
          h6: ({ node, children, ...props }) => (
            <h6 className="text-xs font-medium text-text-muted mt-2 mb-0.5 uppercase tracking-wider first:mt-0" {...props}>
              {children}
            </h6>
          ),

          // Paragraphs
          p: ({ node, children, ...props }) => (
            <p className="leading-relaxed my-2 first:mt-0 last:mb-0 text-text-secondary" {...props}>
              {children}
            </p>
          ),

          // Lists
          ul: ({ node, children, ...props }) => (
            <ul className="list-disc pl-5 my-2 space-y-1 text-text-secondary marker:text-text-dim first:mt-0 last:mb-0 [&_ul]:my-1 [&_ol]:my-1" {...props}>
              {children}
            </ul>
          ),
          ol: ({ node, children, ...props }) => (
            <ol className="list-decimal pl-5 my-2 space-y-1 text-text-secondary marker:text-text-dim first:mt-0 last:mb-0 [&_ul]:my-1 [&_ol]:my-1" {...props}>
              {children}
            </ol>
          ),
          li: ({ node, children, ...props }) => (
            <li className="leading-relaxed pl-0.5" {...props}>
              {children}
            </li>
          ),

          // Blockquotes
          blockquote: ({ node, children, ...props }) => (
            <blockquote className="border-l-2 border-accent-base/70 pl-3.5 py-1.5 my-2.5 text-text-muted italic bg-surface-2/30 rounded-r-md first:mt-0 last:mb-0" {...props}>
              {children}
            </blockquote>
          ),

          // Code blocks & Inline code
          pre: ({ children }) => {
            if (React.isValidElement(children)) {
              const childProps = children.props as { className?: string; children?: React.ReactNode }
              const match = /language-(\w+)/.exec(childProps?.className || '')
              const language = match ? match[1] : undefined
              const codeText = extractTextFromChildren(childProps?.children)
              const cleanCode = codeText.replace(/\n$/, '')
              return <CodeBlock language={language}>{cleanCode}</CodeBlock>
            }
            const rawText = extractTextFromChildren(children).replace(/\n$/, '')
            return <CodeBlock>{rawText}</CodeBlock>
          },
          code: ({ children, ...props }) => {
            return (
              <code
                className="px-1.5 py-0.5 rounded text-[11px] sm:text-xs font-mono bg-surface-2/80 text-text-primary border border-surface-border/60"
                {...props}
              >
                {children}
              </code>
            )
          },

          // Tables
          table: ({ children, ...props }) => (
            <div className="my-3 w-full overflow-x-auto rounded-lg border border-surface-border">
              <table className="w-full border-collapse text-left text-xs text-text-secondary" {...props}>
                {children}
              </table>
            </div>
          ),
          thead: ({ children, ...props }) => (
            <thead className="bg-surface-2/70 border-b border-surface-border text-text-primary font-semibold" {...props}>
              {children}
            </thead>
          ),
          tbody: ({ children, ...props }) => (
            <tbody className="divide-y divide-surface-border/50" {...props}>
              {children}
            </tbody>
          ),
          tr: ({ children, ...props }) => (
            <tr className="hover:bg-surface-2/30 transition-colors" {...props}>
              {children}
            </tr>
          ),
          th: ({ children, style, ...props }) => (
            <th
              style={style}
              className="px-3.5 py-2 text-xs font-semibold tracking-wider text-text-primary whitespace-nowrap"
              {...props}
            >
              {children}
            </th>
          ),
          td: ({ children, style, ...props }) => (
            <td
              style={style}
              className="px-3.5 py-2 text-xs text-text-secondary"
              {...props}
            >
              {children}
            </td>
          ),

          // Links
          a: ({ href, children, ...props }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-focus hover:underline font-medium break-all inline-flex items-center gap-0.5"
              {...props}
            >
              {children}
            </a>
          ),

          // Horizontal rule
          hr: () => <hr className="my-4 border-surface-border" />,

          // Emphasis
          strong: ({ node, children, ...props }) => (
            <strong className="font-semibold text-text-primary" {...props}>
              {children}
            </strong>
          ),
          em: ({ node, children, ...props }) => (
            <em className="italic text-text-secondary" {...props}>
              {children}
            </em>
          ),
          del: ({ node, children, ...props }) => (
            <del className="line-through text-text-muted" {...props}>
              {children}
            </del>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
})

MarkdownRenderer.displayName = 'MarkdownRenderer'
