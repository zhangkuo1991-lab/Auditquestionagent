import { useState, useRef, useEffect } from 'react'
import './InputBar.css'

const SUGGESTIONS = [
  'What does AU-C 315 require for risk assessment?',
  'When do we need to modify our audit opinion?',
  'What are the new SQMS quality management requirements?',
  'How do we audit accounting estimates under SAS 143?',
  'What procedures are required for related party transactions?',
]

export default function InputBar({ onSend, isLoading }) {
  const [text, setText] = useState('')
  const [showSuggestions, setShowSuggestions] = useState(true)
  const textareaRef = useRef(null)

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 140) + 'px'
  }, [text])

  const handleSubmit = () => {
    if (!text.trim() || isLoading) return
    setShowSuggestions(false)
    onSend(text)
    setText('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleSuggestion = (s) => {
    setShowSuggestions(false)
    onSend(s)
  }

  return (
    <div className="input-area">
      {/* Quick suggestions */}
      {showSuggestions && (
        <div className="suggestions">
          <span className="suggestions-label">Try asking:</span>
          <div className="suggestions-chips">
            {SUGGESTIONS.map(s => (
              <button
                key={s}
                className="suggestion-chip"
                onClick={() => handleSuggestion(s)}
                disabled={isLoading}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input row */}
      <div className="input-row">
        <div className="input-box">
          <textarea
            ref={textareaRef}
            className="input-textarea"
            placeholder="Ask about audit standards, procedures, or requirements..."
            value={text}
            onChange={e => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            rows={1}
          />
          <button
            className={`send-btn ${isLoading ? 'loading' : ''}`}
            onClick={handleSubmit}
            disabled={isLoading || !text.trim()}
            title="Send (Enter)"
          >
            {isLoading ? (
              <span className="spinner" />
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            )}
          </button>
        </div>
        <p className="input-hint">Enter to send · Shift+Enter for new line</p>
      </div>
    </div>
  )
}
