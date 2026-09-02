import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Replicate MarkdownRenderer logic for automated headless testing
function extractTextFromChildren(children) {
  if (typeof children === 'string') return children
  if (typeof children === 'number') return String(children)
  if (Array.isArray(children)) {
    return children.map(extractTextFromChildren).join('')
  }
  if (React.isValidElement(children) && children.props && children.props.children) {
    return extractTextFromChildren(children.props.children)
  }
  return ''
}

function TestMarkdownRenderer({ content }) {
  return React.createElement(
    'div',
    { className: 'markdown-content' },
    React.createElement(
      ReactMarkdown,
      {
        remarkPlugins: [remarkGfm],
        components: {
          h1: ({ node, children, ...props }) => React.createElement('h1', { className: 'text-base font-bold', ...props }, children),
          h2: ({ node, children, ...props }) => React.createElement('h2', { className: 'text-sm font-bold', ...props }, children),
          h3: ({ node, children, ...props }) => React.createElement('h3', { className: 'text-xs font-semibold', ...props }, children),
          p: ({ node, children, ...props }) => React.createElement('p', { className: 'leading-relaxed', ...props }, children),
          ul: ({ node, children, ...props }) => React.createElement('ul', { className: 'list-disc pl-5', ...props }, children),
          ol: ({ node, children, ...props }) => React.createElement('ol', { className: 'list-decimal pl-5', ...props }, children),
          li: ({ node, children, ...props }) => React.createElement('li', { className: 'leading-relaxed', ...props }, children),
          blockquote: ({ node, children, ...props }) => React.createElement('blockquote', { className: 'border-l-2', ...props }, children),
          pre: ({ node, children, ...props }) => {
            if (React.isValidElement(children)) {
              const childProps = children.props || {}
              const match = /language-(\w+)/.exec(childProps.className || '')
              const language = match ? match[1] : undefined
              const codeText = extractTextFromChildren(childProps.children).replace(/\n$/, '')
              return React.createElement(
                'div',
                { className: 'code-block-wrapper' },
                language ? React.createElement('div', { className: 'code-header' }, language) : null,
                React.createElement('pre', null, React.createElement('code', null, codeText))
              )
            }
            const rawText = extractTextFromChildren(children).replace(/\n$/, '')
            return React.createElement('pre', null, React.createElement('code', null, rawText))
          },
          code: ({ node, className, children, ...props }) =>
            React.createElement('code', { className: 'inline-code', ...props }, children),
          table: ({ node, children, ...props }) =>
            React.createElement('div', { className: 'table-scroll-wrapper' }, React.createElement('table', props, children)),
          thead: ({ node, children, ...props }) => React.createElement('thead', props, children),
          tbody: ({ node, children, ...props }) => React.createElement('tbody', props, children),
          tr: ({ node, children, ...props }) => React.createElement('tr', props, children),
          th: ({ node, children, style, ...props }) => React.createElement('th', { style, ...props }, children),
          td: ({ node, children, style, ...props }) => React.createElement('td', { style, ...props }, children),
          a: ({ node, href, children, ...props }) =>
            React.createElement('a', { href, target: '_blank', rel: 'noopener noreferrer', ...props }, children),
          hr: ({ node, ...props }) => React.createElement('hr', props),
          strong: ({ node, children, ...props }) => React.createElement('strong', props, children),
          em: ({ node, children, ...props }) => React.createElement('em', props, children),
          del: ({ node, children, ...props }) => React.createElement('del', props, children),
        },
      },
      content
    )
  )
}

function runTests() {
  console.log('====================================================')
  console.log('  GOAL 9.5 RESPONSE PRESENTATION & FORMATTING TESTS')
  console.log('====================================================\n')

  let passed = 0
  let failed = 0

  function assert(condition, message) {
    if (condition) {
      console.log(`  [PASS] ${message}`)
      passed++
    } else {
      console.error(`  [FAIL] ${message}`)
      failed++
    }
  }

  // TEST A: Normal paragraph with multiple sentences
  console.log('--- TEST A: Normal Paragraph ---')
  const testA = `This is the first sentence of the response. Here is a second sentence providing additional context. Finally, this is the third sentence wrapping up the paragraph.`
  const htmlA = renderToStaticMarkup(React.createElement(TestMarkdownRenderer, { content: testA }))
  assert(htmlA.includes('<p class="leading-relaxed">This is the first sentence'), 'Paragraph rendered in <p>')
  assert(htmlA.includes('wrapping up the paragraph.</p>'), 'Paragraph ends cleanly')

  // TEST B: Headings, bold text, italic text
  console.log('\n--- TEST B: Headings, Bold, Italic ---')
  const testB = `# Main Heading\n\n## Subheading\n\n### Section 3\n\nThis is **bold text** and this is *italic text* and ~~strikethrough~~.`
  const htmlB = renderToStaticMarkup(React.createElement(TestMarkdownRenderer, { content: testB }))
  assert(htmlB.includes('<h1 class="text-base font-bold">Main Heading</h1>'), 'H1 rendered correctly')
  assert(htmlB.includes('<h2 class="text-sm font-bold">Subheading</h2>'), 'H2 rendered correctly')
  assert(htmlB.includes('<h3 class="text-xs font-semibold">Section 3</h3>'), 'H3 rendered correctly')
  assert(htmlB.includes('<strong>bold text</strong>'), 'Bold text rendered in <strong>')
  assert(htmlB.includes('<em>italic text</em>'), 'Italic text rendered in <em>')
  assert(htmlB.includes('<del>strikethrough</del>'), 'Strikethrough rendered in <del>')

  // TEST C: Numbered list with nested bullet points
  console.log('\n--- TEST C: Lists & Nested Lists ---')
  const testC = `1. Step One\n   - Detail A\n   - Detail B\n2. Step Two\n   - Detail C`
  const htmlC = renderToStaticMarkup(React.createElement(TestMarkdownRenderer, { content: testC }))
  assert(htmlC.includes('<ol class="list-decimal pl-5">'), 'Ordered list rendered with <ol>')
  assert(htmlC.includes('<ul class="list-disc pl-5">'), 'Nested unordered list rendered with <ul>')
  assert(htmlC.includes('Step One'), 'Step One content preserved')
  assert(htmlC.includes('Detail A'), 'Detail A nested content preserved')

  // TEST D: Technical explanation containing arrows, comparison, math symbols, %, &, <, >
  console.log('\n--- TEST D: Special Characters & Technical Symbols ---')
  const testD = `Technical analysis:\n→ Input leads to output ←\nComparison: A ≤ B and C ≥ D, while X ≠ Y and M ≈ N\nMath: π * r^2, √16 = 4, ∑(x_i)\nTemperature: 25°C ± 2°C\nOperators: 10 × 5 ÷ 2 = 25\nMetrics: 99.9% uptime & latency < 50ms (greater > lesser)\nQuotes: "double" and 'single'`
  const htmlD = renderToStaticMarkup(React.createElement(TestMarkdownRenderer, { content: testD }))
  assert(htmlD.includes('→ Input leads to output ←'), 'Arrows preserved')
  assert(htmlD.includes('A ≤ B and C ≥ D, while X ≠ Y and M ≈ N'), 'Comparison symbols preserved')
  assert(htmlD.includes('π * r^2, √16 = 4, ∑(x_i)'), 'Math symbols preserved')
  assert(htmlD.includes('25°C ± 2°C'), 'Degree and plusminus preserved')
  assert(htmlD.includes('10 × 5 ÷ 2 = 25'), 'Math operators preserved')
  assert(htmlD.includes('99.9% uptime &amp; latency &lt; 50ms (greater &gt; lesser)'), '%, &, <, > safely encoded and visible')

  // TEST E: Code block
  console.log('\n--- TEST E: Code Blocks ---')
  const testE = "```python\ndef calculate_fibonacci(n: int) -> int:\n    if n <= 1:\n        return n\n    return calculate_fibonacci(n - 1) + calculate_fibonacci(n - 2)\n```"
  const htmlE = renderToStaticMarkup(React.createElement(TestMarkdownRenderer, { content: testE }))
  assert(htmlE.includes('<div class="code-header">python</div>'), 'Language header detected as python')
  assert(htmlE.includes('def calculate_fibonacci(n: int) -&gt; int:'), 'Code content rendered inside <code>')
  assert(htmlE.includes('    if n &lt;= 1:'), 'Indentation and whitespace strictly preserved')

  // TEST F: Markdown table
  console.log('\n--- TEST F: Markdown Tables ---')
  const testF = `| Metric | Target | Actual |\n| :--- | :---: | ---: |\n| Latency | < 50ms | 42ms |\n| Accuracy | > 95% | 98.4% |\n| Uptime | 99.9% | 99.95% |`
  const htmlF = renderToStaticMarkup(React.createElement(TestMarkdownRenderer, { content: testF }))
  assert(htmlF.includes('<div class="table-scroll-wrapper"><table>'), 'Table wrapper rendered')
  assert(htmlF.includes('Metric</th>'), 'Table header Metric')
  assert(htmlF.includes('Target</th>'), 'Table header Target')
  assert(htmlF.includes('Actual</th>'), 'Table header Actual')
  assert(htmlF.includes('&lt; 50ms</td>'), 'Table cell with < safely rendered')
  assert(htmlF.includes('98.4%</td>'), 'Table cell values preserved')

  // TEST G: Emojis
  console.log('\n--- TEST G: Emojis ---')
  const testG = `🚀 Deployment succeeded! 💡 Tip: Keep memory usage below 512MB. ⚡ Super fast!`
  const htmlG = renderToStaticMarkup(React.createElement(TestMarkdownRenderer, { content: testG }))
  assert(htmlG.includes('🚀 Deployment succeeded!'), 'Rocket emoji preserved')
  assert(htmlG.includes('💡 Tip:'), 'Bulb emoji preserved')
  assert(htmlG.includes('⚡ Super fast!'), 'Lightning emoji preserved')

  // TEST H: Long structured response
  console.log('\n--- TEST H: Long Structured Response ---')
  const testH = `# Architectural Specification\n\n## 1. Overview\nThe system distributes workloads across 3 worker nodes.\n\n## 2. Key Components\n- **Router**: Directs traffic based on path.\n- **Worker Pool**: Executes asynchronous jobs.\n- **Cache**: In-memory Redis instance.\n\n> Note: All nodes must run with synchronized system clocks.\n\n\`\`\`typescript\ninterface WorkerConfig {\n  id: string;\n  concurrency: number;\n}\n\`\`\`\n\n| Component | Replicas | Status |\n| :--- | :---: | :--- |\n| Router | 2 | Healthy |\n| Worker | 5 | Active |\n\nFor more information, visit [Documentation](https://example.com/docs).`
  const htmlH = renderToStaticMarkup(React.createElement(TestMarkdownRenderer, { content: testH }))
  assert(htmlH.includes('Architectural Specification</h1>'), 'Main title in H1')
  assert(htmlH.includes('Overview</h2>'), 'Section in H2')
  assert(htmlH.includes('<strong>Router</strong>'), 'Bold list items')
  assert(htmlH.includes('<blockquote class="border-l-2">'), 'Blockquote rendered')
  assert(htmlH.includes('<div class="code-header">typescript</div>'), 'Typescript code block')
  assert(htmlH.includes('<table>'), 'Table in structured response')
  assert(htmlH.includes('<a href="https://example.com/docs" target="_blank" rel="noopener noreferrer">Documentation</a>'), 'Safe external link with target and rel')

  // TEST I: HTML-sensitive characters & Security
  console.log('\n--- TEST I: Security & HTML Escaping ---')
  const testI = `Test unsafe input:\n<script>alert("XSS")</script>\n<div onclick="alert('XSS')">Click me</div>\n[Malicious Link](javascript:alert('XSS'))\nSafe logic: x < 10 && y > 20`
  const htmlI = renderToStaticMarkup(React.createElement(TestMarkdownRenderer, { content: testI }))
  assert(!htmlI.includes('<script>alert'), 'Raw <script> tag is NOT executed or rendered as live DOM element')
  assert(!htmlI.includes('onclick="alert'), 'Raw onclick handler is NOT injected into DOM')
  assert(!htmlI.includes('href="javascript:'), 'javascript: URL scheme is completely neutralized')
  assert(htmlI.includes('x &lt; 10 &amp;&amp; y &gt; 20'), 'Safe logic characters <, >, && encoded cleanly')

  // TEST J: Mixed Markdown with Code and Special Characters
  console.log('\n--- TEST J: Mixed Markdown & Code ---')
  const testJ = `### Performance Benchmark (Q3 2026)\n\nWe achieved a **35% speedup** (latency: 120ms → 78ms at 99.9th percentile).\n\n\`\`\`json\n{\n  "status": "success",\n  "threshold": "<= 80ms",\n  "symbols": "α, β, γ"\n}\n\`\`\`\n\nInline check: Use \`validateThreshold(t <= 80)\` for strict bounds.`
  const htmlJ = renderToStaticMarkup(React.createElement(TestMarkdownRenderer, { content: testJ }))
  assert(htmlJ.includes('Performance Benchmark (Q3 2026)</h3>'), 'H3 heading')
  assert(htmlJ.includes('<strong>35% speedup</strong>'), 'Bold percentage')
  assert(htmlJ.includes('120ms → 78ms'), 'Arrow in paragraph')
  assert(htmlJ.includes('&quot;threshold&quot;: &quot;&lt;= 80ms&quot;'), 'Code block JSON content')
  assert(htmlJ.includes('<code class="inline-code">validateThreshold(t &lt;= 80)</code>'), 'Inline code block with special symbols')

  console.log('\n====================================================')
  console.log(`  SUMMARY: ${passed} PASSED, ${failed} FAILED`)
  console.log('====================================================')

  if (failed > 0) {
    process.exit(1)
  }
}

runTests()
