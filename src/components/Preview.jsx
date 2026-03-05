import { useState, useEffect, useRef, useCallback } from 'react'
import { marked } from 'marked'
import hljs from 'highlight.js'

// Configure marked with highlight.js
marked.setOptions({
  breaks: true,
  gfm: true,
})

const renderer = new marked.Renderer()

renderer.code = function({ text, lang }) {
  const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
  let highlighted
  try {
    highlighted = hljs.highlight(text, { language }).value
  } catch {
    highlighted = hljs.highlightAuto(text).value
  }
  const langLabel = lang || 'text'
  return `<div class="code-block-wrap">
    <div class="code-block-header">
      <span class="code-lang">${langLabel}</span>
      <button class="copy-btn" data-code="${encodeURIComponent(text)}">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
        </svg>
        Copy
      </button>
    </div>
    <pre><code class="hljs language-${language}">${highlighted}</code></pre>
  </div>`
}

renderer.heading = function({ text, depth }) {
  const slug = text.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-')
  return `<h${depth} id="heading-${slug}">${text}</h${depth}>`
}

marked.use({ renderer })

function extractTOC(markdown) {
  const headingRegex = /^(#{1,4})\s+(.+)$/gm
  const headings = []
  let match
  while ((match = headingRegex.exec(markdown)) !== null) {
    const level = match[1].length
    const text = match[2].trim()
    const slug = text.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-')
    headings.push({ level, text, id: `heading-${slug}` })
  }
  return headings
}

function countWords(text) {
  return text.trim().split(/\s+/).filter(Boolean).length
}

const CopyIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
  </svg>
)

const CheckIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12"/>
  </svg>
)

export default function Preview({ file, showTOC }) {
  const [tab, setTab] = useState('preview')
  const [toc, setToc] = useState([])
  const [copiedAll, setCopiedAll] = useState(false)
  const previewRef = useRef(null)

  useEffect(() => {
    if (file) {
      setToc(extractTOC(file.content))
      setTab('preview')
    }
  }, [file?.id])

  // Handle copy buttons inside rendered markdown
  useEffect(() => {
    const el = previewRef.current
    if (!el) return

    const handler = (e) => {
      const btn = e.target.closest('.copy-btn')
      if (!btn) return
      const code = decodeURIComponent(btn.dataset.code || '')
      navigator.clipboard.writeText(code).then(() => {
        btn.classList.add('copied')
        btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Copied!`
        setTimeout(() => {
          btn.classList.remove('copied')
          btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy`
        }, 2000)
      })
    }

    el.addEventListener('click', handler)
    return () => el.removeEventListener('click', handler)
  }, [tab])

  const scrollToHeading = useCallback((id) => {
    const el = previewRef.current?.querySelector(`#${id}`)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [])

  const copyAll = () => {
    navigator.clipboard.writeText(file.content).then(() => {
      setCopiedAll(true)
      setTimeout(() => setCopiedAll(false), 2000)
    })
  }

  if (!file) return null

  const html = marked.parse(file.content)
  const wordCount = countWords(file.content)
  const lines = file.content.split('\n').length
  const readTime = Math.max(1, Math.ceil(wordCount / 200))

  return (
    <div className="preview-wrapper">
      <div className="preview-container">
        <div className="preview-header">
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="preview-filename">{file.name}</div>
            <div className="preview-meta">{wordCount.toLocaleString()} words · {lines} lines · {readTime} min read</div>
          </div>

          <button className="btn btn-ghost" onClick={copyAll} style={{ fontSize: 12, padding: '5px 10px' }}>
            {copiedAll ? <><CheckIcon /> Copied!</> : <><CopyIcon /> Copy all</>}
          </button>

          <div className="preview-tabs">
            <button className={`preview-tab${tab === 'preview' ? ' active' : ''}`} onClick={() => setTab('preview')}>Preview</button>
            <button className={`preview-tab${tab === 'raw' ? ' active' : ''}`} onClick={() => setTab('raw')}>Raw</button>
          </div>
        </div>

        {tab === 'preview' ? (
          <div className="preview-scroll" ref={previewRef}>
            <div
              className="markdown-body"
              dangerouslySetInnerHTML={{ __html: html }}
            />
          </div>
        ) : (
          <div className="raw-content">
            <pre>{file.content}</pre>
          </div>
        )}
      </div>

      {showTOC && toc.length > 0 && (
        <div className="toc-panel">
          <div className="toc-title">Contents</div>
          {toc.map((item, i) => (
            <button
              key={i}
              className="toc-item"
              data-level={item.level}
              onClick={() => scrollToHeading(item.id)}
              title={item.text}
            >
              {item.text}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
