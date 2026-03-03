import { useState, useCallback, useRef } from 'react'
import Sidebar from './components/Sidebar'
import Preview from './components/Preview'
import './App.css'

let idCounter = 0
const uid = () => ++idCounter

// ── Icons ────────────────────────────────────────────────
const LogoIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
    <polyline points="14 2 14 8 20 8"/>
    <line x1="16" y1="13" x2="8" y2="13"/>
    <line x1="16" y1="17" x2="8" y2="17"/>
    <line x1="10" y1="9" x2="8" y2="9"/>
  </svg>
)

const SunIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="5"/>
    <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
    <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
  </svg>
)

const MoonIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
  </svg>
)

const SidebarIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
    <line x1="9" y1="3" x2="9" y2="21"/>
  </svg>
)

const TOCIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/>
    <line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
  </svg>
)

const FolderOpenIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
    <line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/>
  </svg>
)

const UploadCloudIcon = () => (
  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/>
    <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/>
  </svg>
)

const BigFileIcon = () => (
  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
    <polyline points="14 2 14 8 20 8"/>
  </svg>
)

// ── Welcome Screen ───────────────────────────────────────
function Welcome({ onOpen }) {
  return (
    <div className="welcome">
      <div className="welcome-inner">
        <div className="welcome-icon">
          <BigFileIcon />
        </div>
        <h2>Markdown Reader</h2>
        <p>Open any <code style={{ background: 'var(--bg-tertiary)', padding: '2px 6px', borderRadius: 4, fontSize: 13 }}>.md</code> file to start reading with a beautiful, distraction-free experience.</p>
        <div className="welcome-actions">
          <button className="btn btn-primary" onClick={onOpen}>
            <FolderOpenIcon /> Open File
          </button>
        </div>
        <div className="welcome-features">
          <div className="feature-card">
            <BigFileIcon style={{ width: 18, height: 18 }} />
            <h4>Multiple Files</h4>
            <p>Open and switch between multiple .md files easily.</p>
          </div>
          <div className="feature-card">
            <TOCIcon />
            <h4>Table of Contents</h4>
            <p>Auto-generated navigation from your headings.</p>
          </div>
          <div className="feature-card">
            <SunIcon />
            <h4>Dark & Light</h4>
            <p>Toggle between dark and light themes.</p>
          </div>
          <div className="feature-card">
            <FolderOpenIcon />
            <h4>Drag & Drop</h4>
            <p>Drop .md files anywhere to open them instantly.</p>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Main App ─────────────────────────────────────────────
export default function App() {
  const [theme, setTheme] = useState('dark')
  const [files, setFiles] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [showTOC, setShowTOC] = useState(true)
  const [dragging, setDragging] = useState(false)
  const fileInputRef = useRef(null)
  const dragCounterRef = useRef(0)

  const activeFile = files.find(f => f.id === activeId) || null

  const toggleTheme = () => {
    setTheme(t => t === 'dark' ? 'light' : 'dark')
  }

  const loadFiles = useCallback((fileList) => {
    const mdFiles = Array.from(fileList).filter(f =>
      f.name.endsWith('.md') || f.name.endsWith('.markdown')
    )
    if (mdFiles.length === 0) return

    Promise.all(mdFiles.map(f => f.text().then(content => ({
      id: uid(),
      name: f.name,
      content,
    })))).then(loaded => {
      setFiles(prev => {
        const existingNames = new Set(prev.map(f => f.name))
        const fresh = loaded.filter(f => !existingNames.has(f.name))
        const merged = [...prev, ...fresh]
        if (fresh.length > 0) setActiveId(fresh[fresh.length - 1].id)
        return merged
      })
    })
  }, [])

  const openFilePicker = () => {
    fileInputRef.current?.click()
  }

  const onInputChange = (e) => {
    if (e.target.files?.length) {
      loadFiles(e.target.files)
      e.target.value = ''
    }
  }

  const removeFile = (id) => {
    setFiles(prev => {
      const next = prev.filter(f => f.id !== id)
      if (id === activeId) {
        setActiveId(next.length > 0 ? next[next.length - 1].id : null)
      }
      return next
    })
  }

  // Drag & drop
  const onDragEnter = (e) => {
    e.preventDefault()
    dragCounterRef.current++
    if (e.dataTransfer.types.includes('Files')) setDragging(true)
  }
  const onDragLeave = (e) => {
    e.preventDefault()
    dragCounterRef.current--
    if (dragCounterRef.current === 0) setDragging(false)
  }
  const onDragOver = (e) => { e.preventDefault() }
  const onDrop = (e) => {
    e.preventDefault()
    dragCounterRef.current = 0
    setDragging(false)
    if (e.dataTransfer.files?.length) loadFiles(e.dataTransfer.files)
  }

  const statusWords = activeFile
    ? activeFile.content.trim().split(/\s+/).filter(Boolean).length
    : 0

  return (
    <div
      className="app"
      data-theme={theme}
      onDragEnter={onDragEnter}
      onDragLeave={onDragLeave}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".md,.markdown"
        multiple
        style={{ display: 'none' }}
        onChange={onInputChange}
      />

      {/* ── Toolbar ── */}
      <header className="toolbar">
        <div className="toolbar-logo">
          <LogoIcon />
          <span>MarkReader</span>
        </div>
        <div className="toolbar-divider" />

        <button
          className={`btn-icon${sidebarOpen ? ' active' : ''}`}
          onClick={() => setSidebarOpen(o => !o)}
          title="Toggle sidebar"
        >
          <SidebarIcon />
        </button>

        <button
          className={`btn-icon${showTOC ? ' active' : ''}`}
          onClick={() => setShowTOC(o => !o)}
          title="Toggle table of contents"
        >
          <TOCIcon />
        </button>

        <div className="toolbar-spacer" />

        <div className="toolbar-actions">
          <button className="btn btn-primary" onClick={openFilePicker}>
            <FolderOpenIcon /> Open File
          </button>
          <button className="btn-icon" onClick={toggleTheme} title="Toggle theme">
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
          </button>
        </div>
      </header>

      {/* ── Body ── */}
      <div className="layout">
        <Sidebar
          files={files}
          activeId={activeId}
          onSelect={setActiveId}
          onRemove={removeFile}
          collapsed={!sidebarOpen}
        />

        <main className="main">
          <div className={`drop-overlay${dragging ? ' visible' : ''}`}>
            <div className="drop-overlay-inner">
              <UploadCloudIcon />
              <p>Drop .md files here</p>
            </div>
          </div>

          {activeFile ? (
            <Preview file={activeFile} showTOC={showTOC} />
          ) : (
            <Welcome onOpen={openFilePicker} />
          )}
        </main>
      </div>

      {/* ── Status Bar ── */}
      <footer className="statusbar">
        <span>
          {activeFile ? (
            <><b>{activeFile.name}</b> · {statusWords.toLocaleString()} words</>
          ) : (
            <><b>{files.length}</b> file{files.length !== 1 ? 's' : ''} open</>
          )}
        </span>
        <span>Markdown Reader</span>
      </footer>
    </div>
  )
}
