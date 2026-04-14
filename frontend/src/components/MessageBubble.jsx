import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './MessageBubble.css'

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  const [showLog, setShowLog] = useState(false)

  const time = new Date(message.timestamp).toLocaleTimeString([], {
    hour: '2-digit', minute: '2-digit'
  })

  const hasSources = !isUser && message.sources?.length > 0

  return (
    <div className={`message-row ${isUser ? 'user' : 'assistant'}`}>
      {!isUser && (
        <div className="avatar agent-avatar" title="AuditIQ Agent">⚖️</div>
      )}

      <div className="bubble-wrapper">
        {/* Agent + RAG tags */}
        {!isUser && message.agents_used?.length > 0 && (
          <div className="agent-tags">
            {message.agents_used.map(name => (
              <span key={name} className="agent-tag">{name}</span>
            ))}
            {message.rag_used && (
              <span className="agent-tag rag-tag">📄 RAG</span>
            )}
          </div>
        )}

        {/* Message bubble */}
        <div className={`bubble ${isUser ? 'user-bubble' : 'agent-bubble'}`}>
          {isUser ? (
            <p className="user-text">{message.content}</p>
          ) : (
            <div className="markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Source citations */}
        {hasSources && (
          <div className="sources-panel">
            <div className="sources-title">📎 Sources — AICPA AU-C Standards (2025)</div>
            <div className="sources-list">
              {message.sources.map((src, i) => {
                const pageLabel = src.pages?.length === 1
                  ? `p. ${src.pages[0]}`
                  : src.pages?.length > 1
                    ? `pp. ${src.pages[0]}–${src.pages[src.pages.length - 1]}`
                    : ''
                return (
                  <div key={i} className="source-chip">
                    <span className="source-section">{src.section}</span>
                    <span className="source-title">{src.title}</span>
                    {pageLabel && <span className="source-page">{pageLabel}</span>}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="bubble-footer">
          <span className="msg-time">{time}</span>
          {!isUser && message.agent_logs?.length > 0 && (
            <button className="log-toggle" onClick={() => setShowLog(v => !v)}>
              {showLog ? '▲ Hide agent log' : '▼ View agent log'}
            </button>
          )}
        </div>

        {/* Agent log */}
        {showLog && message.agent_logs?.length > 0 && (
          <div className="agent-log-panel">
            <div className="log-panel-title">🔍 Agent Trace</div>
            {message.agent_logs.map((entry, i) => (
              <div key={i} className="log-panel-entry">
                <span className="lp-agent">{entry.agent}</span>
                <span className="lp-arrow">→</span>
                <span className="lp-action">{entry.action}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {isUser && (
        <div className="avatar user-avatar" title="You">👤</div>
      )}
    </div>
  )
}
