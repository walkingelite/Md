import { useEffect, useRef, useState } from 'react'
import ePub from 'epubjs'

const ChevronLeftIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="15 18 9 12 15 6"/>
  </svg>
)

const ChevronRightIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="9 18 15 12 9 6"/>
  </svg>
)

export default function EpubViewer({ file }) {
  const containerRef = useRef(null)
  const bookRef = useRef(null)
  const renditionRef = useRef(null)
  const [title, setTitle] = useState(file.name)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!containerRef.current) return

    const book = ePub(file.url)
    bookRef.current = book

    const rendition = book.renderTo(containerRef.current, {
      width: '100%',
      height: '100%',
      spread: 'none',
    })
    renditionRef.current = rendition

    book.ready.then(() => {
      return book.loaded.metadata
    }).then((metadata) => {
      if (metadata?.title) setTitle(metadata.title)
      setLoading(false)
    }).catch((err) => {
      setError(`Could not load ePub: ${err.message}`)
      setLoading(false)
    })

    rendition.display().catch((err) => {
      setError(`Could not render ePub: ${err.message}`)
      setLoading(false)
    })

    return () => {
      rendition.destroy()
      book.destroy()
    }
  }, [file.url])

  const prev = () => renditionRef.current?.prev()
  const next = () => renditionRef.current?.next()

  return (
    <div className="epub-viewer">
      <div className="preview-header">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="preview-filename">{title}</div>
          <div className="preview-meta">EPUB · {file.name}</div>
        </div>
      </div>

      <div className="epub-body">
        {loading && (
          <div className="epub-loading">
            <div className="epub-loading-spinner" />
            <span>Loading ePub…</span>
          </div>
        )}
        {error && (
          <div className="epub-error">
            <p>{error}</p>
          </div>
        )}
        <div ref={containerRef} className="epub-render" style={{ visibility: loading || error ? 'hidden' : 'visible' }} />
        {!loading && !error && (
          <div className="epub-nav">
            <button className="btn-icon" onClick={prev} title="Previous page"><ChevronLeftIcon /></button>
            <button className="btn-icon" onClick={next} title="Next page"><ChevronRightIcon /></button>
          </div>
        )}
      </div>
    </div>
  )
}
