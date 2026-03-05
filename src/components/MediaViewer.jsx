const MusicIcon = () => (
  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 18V5l12-2v13"/>
    <circle cx="6" cy="18" r="3"/>
    <circle cx="18" cy="16" r="3"/>
  </svg>
)

const FileBinaryIcon = () => (
  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
    <polyline points="14 2 14 8 20 8"/>
    <path d="M8 13h1v4H8z"/><path d="M12 13c0 0 1 0 1 2s-1 2-1 2h1"/>
  </svg>
)

export default function MediaViewer({ file }) {
  return (
    <div className="media-viewer">
      <div className="preview-header">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="preview-filename">{file.name}</div>
          <div className="preview-meta">{file.type.toUpperCase()}</div>
        </div>
      </div>

      <div className="media-viewer-body">
        {file.type === 'image' && (
          <div className="media-image-wrap">
            <img src={file.url} alt={file.name} className="media-image" />
          </div>
        )}

        {file.type === 'video' && (
          <div className="media-video-wrap">
            <video src={file.url} controls className="media-video">
              Your browser does not support this video format.
            </video>
          </div>
        )}

        {file.type === 'audio' && (
          <div className="media-audio-wrap">
            <div className="media-audio-inner">
              <div className="media-audio-icon">
                <MusicIcon />
              </div>
              <div className="media-audio-name">{file.name}</div>
              <audio src={file.url} controls className="media-audio">
                Your browser does not support this audio format.
              </audio>
            </div>
          </div>
        )}

        {file.type === 'pdf' && (
          <embed
            src={file.url}
            type="application/pdf"
            className="media-pdf"
          />
        )}

        {file.type === 'book' && (
          <div className="media-unsupported">
            <FileBinaryIcon />
            <p>This book format cannot be previewed in the browser.</p>
            <span>Supported ebook format: .epub — Convert .mobi/.azw/.azw3 to EPUB to read here.</span>
          </div>
        )}
      </div>
    </div>
  )
}
