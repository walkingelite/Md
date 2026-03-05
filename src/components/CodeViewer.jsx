import { useState, useMemo } from 'react'
import hljs from 'highlight.js'

const LANG_MAP = {
  js: 'javascript', jsx: 'javascript', mjs: 'javascript', cjs: 'javascript',
  ts: 'typescript', tsx: 'typescript',
  py: 'python', rb: 'ruby', rs: 'rust', go: 'go',
  java: 'java', kt: 'kotlin', swift: 'swift',
  c: 'c', cpp: 'cpp', cc: 'cpp', h: 'c', hpp: 'cpp',
  cs: 'csharp', php: 'php', r: 'r', lua: 'lua',
  css: 'css', scss: 'scss', less: 'less',
  html: 'html', htm: 'html', xml: 'xml',
  json: 'json', yaml: 'yaml', yml: 'yaml', toml: 'ini',
  sql: 'sql', sh: 'bash', bash: 'bash', zsh: 'bash', fish: 'bash',
  ps1: 'powershell', bat: 'dos',
  dockerfile: 'dockerfile',
  graphql: 'graphql', gql: 'graphql',
  txt: 'plaintext', csv: 'plaintext', log: 'plaintext',
  env: 'bash', gitignore: 'bash',
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

export default function CodeViewer({ file }) {
  const [copied, setCopied] = useState(false)

  const ext = file.name.split('.').pop().toLowerCase()
  const lang = LANG_MAP[ext] || 'plaintext'

  const highlighted = useMemo(() => {
    const safeLang = hljs.getLanguage(lang) ? lang : 'plaintext'
    try {
      return hljs.highlight(file.content, { language: safeLang }).value
    } catch {
      return hljs.highlightAuto(file.content).value
    }
  }, [file.content, lang])

  const lineCount = useMemo(() => file.content.split('\n').length, [file.content])

  const copyAll = () => {
    navigator.clipboard.writeText(file.content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="code-viewer">
      <div className="preview-header">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="preview-filename">{file.name}</div>
          <div className="preview-meta">{lineCount} lines · {lang}</div>
        </div>
        <button className="btn btn-ghost" onClick={copyAll} style={{ fontSize: 12, padding: '5px 10px' }}>
          {copied ? <><CheckIcon /> Copied!</> : <><CopyIcon /> Copy all</>}
        </button>
      </div>

      <div className="code-viewer-body">
        <div className="code-viewer-gutter">
          {Array.from({ length: lineCount }, (_, i) => (
            <span key={i}>{i + 1}</span>
          ))}
        </div>
        <pre className="code-viewer-pre">
          <code
            className={`hljs language-${lang}`}
            dangerouslySetInnerHTML={{ __html: highlighted }}
          />
        </pre>
      </div>
    </div>
  )
}
