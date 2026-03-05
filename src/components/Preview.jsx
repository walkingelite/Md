import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { writeToClipboard } from '../utils/clipboard'
import { marked } from 'marked'
import markedAlert from 'marked-alert'
import markedFootnote from 'marked-footnote'
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
  const id = `heading-${slug}`
  return `<h${depth} id="${id}">
    <a class="heading-anchor" href="#${id}" title="Copy link to section">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
      </svg>
    </a>${text}</h${depth}>`
}

marked.use({ renderer })
marked.use(markedAlert())
marked.use(markedFootnote())

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
  const [copiedAll, setCopiedAll] = useState(false)
  const [progress, setProgress] = useState(0)
  const previewRef = useRef(null)

  const toc = useMemo(() => (file ? extractTOC(file.content) : []), [file])

  // Reading progress bar
  useEffect(() => {
    const el = previewRef.current
    if (!el) return
    const onScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = el
      const max = scrollHeight - clientHeight
      setProgress(max > 0 ? scrollTop / max : 0)
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [tab])

  // Handle copy buttons inside rendered markdown
  useEffect(() => {
    const el = previewRef.current
    if (!el) return

    const handler = (e) => {
      const btn = e.target.closest('.copy-btn')
      if (!btn) return
      const code = decodeURIComponent(btn.dataset.code || '')
      writeToClipboard(code).then(() => {
        btn.classList.add('copied')
        btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Copied!`
        setTimeout(() => {
          btn.classList.remove('copied')
          btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy`
        }, 2000)
      })
    }

    // Handle heading anchor clicks — copy URL to clipboard
    const anchorHandler = (e) => {
      const a = e.target.closest('.heading-anchor')
      if (!a) return
      e.preventDefault()
      const url = window.location.href.split('#')[0] + a.getAttribute('href')
      writeToClipboard(url)
      const svg = a.querySelector('svg')
      if (svg) {
        svg.style.color = 'var(--success)'
        setTimeout(() => { svg.style.color = '' }, 1500)
      }
    }

    el.addEventListener('click', handler)
    el.addEventListener('click', anchorHandler)
    return () => {
      el.removeEventListener('click', handler)
      el.removeEventListener('click', anchorHandler)
    }
  }, [tab])

  const scrollToHeading = useCallback((id) => {
    const el = previewRef.current?.querySelector(`#${id}`)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [])

  const copyAll = () => {
    writeToClipboard(file.content).then(() => {
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
        <div className="reading-progress">
          <div className="reading-progress-bar" style={{ width: `${progress * 100}%` }} />
        </div>

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
