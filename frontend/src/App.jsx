import { useState, useRef, useEffect } from 'react'
import ChatWindow from './components/ChatWindow'
import InputBar from './components/InputBar'
import './App.css'

const WELCOME_MESSAGE = {
  id: 'welcome',
  role: 'assistant',
  content: `Welcome to **AuditIQ** — your AI-powered audit knowledge assistant.

I can help you with:
- 📋 **GAAS standards** and AU-C section requirements
- 🔍 **Risk assessment** procedures (AU-C 315, SAS 145)
- 📝 **Audit reporting** — opinions, modifications, going concern
- 🛡️ **Fraud & compliance** responsibilities
- 🆕 **Recent standard updates** (SQMS, SAS 143, SAS 145)

Upload the AICPA AU-C Standards PDF in the sidebar to enable **RAG** — answers grounded directly in the official document with page references.`,
  agents_used: [],
  agent_logs: [],
  sources: [],
  rag_used: false,
  timestamp: new Date().toISOString(),
}

export default function App() {
  const [messages, setMessages]   = useState([WELCOME_MESSAGE])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError]         = useState(null)
  const [kbStatus, setKbStatus]   = useState(null)   // { indexed, chunk_count, source }
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef(null)

  // ── Poll KB status on mount ──────────────────────────────────────────────
  useEffect(() => {
    fetch('/api/ingest/status')
      .then(r => r.json())
      .then(setKbStatus)
      .catch(() => {})
  }, [])

  // ── Chat ─────────────────────────────────────────────────────────────────
  const handleSend = async (text) => {
    if (!text.trim() || isLoading) return

    const userMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: text.trim(),
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)
    setError(null)

    const history = messages
      .filter(m => m.id !== 'welcome')
      .map(m => ({ role: m.role, content: m.content }))

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text.trim(), history }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Server error')
      }
      const data = await res.json()
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content:    data.response,
        agents_used: data.agents_used || [],
        agent_logs:  data.agent_logs  || [],
        sources:     data.sources     || [],
        rag_used:    data.rag_used    || false,
        timestamp: new Date().toISOString(),
      }])
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  // ── PDF upload ───────────────────────────────────────────────────────────
  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch('/api/ingest', { method: 'POST', body: fd })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Ingestion failed')
      }
      const data = await res.json()
      setKbStatus({ indexed: true, chunk_count: data.chunk_count, source: data.source })
    } catch (err) {
      setError(`Upload failed: ${err.message}`)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleClear = () => {
    setMessages([WELCOME_MESSAGE])
    setError(null)
  }

  const lastAgentMessage = [...messages].reverse().find(
    m => m.role === 'assistant' && m.agent_logs?.length > 0
  )

  return (
    <div className="app-layout">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <span className="logo-icon">⚖️</span>
          <div>
            <div className="logo-title">AuditIQ</div>
            <div className="logo-sub">Knowledge Assistant</div>
          </div>
        </div>

        {/* Agents */}
        <nav className="sidebar-nav">
          <div className="nav-label">AGENTS</div>
          <AgentBadge name="Manager Agent"    icon="🧠" desc="Routes & synthesises" active />
          <AgentBadge name="Audit Standards"  icon="📚" desc="GAAS · AU-C · SAS"    active />
          <AgentBadge name="RAG Retriever"    icon="🔍" desc="BM25 over PDF"         active={kbStatus?.indexed} />
        </nav>

        {/* Knowledge Base */}
        <div className="kb-section">
          <div className="nav-label">KNOWLEDGE BASE</div>
          {kbStatus?.indexed ? (
            <div className="kb-status indexed">
              <span className="kb-dot" />
              <div>
                <div className="kb-label">Indexed ✓</div>
                <div className="kb-meta">{kbStatus.chunk_count?.toLocaleString()} chunks · {kbStatus.source}</div>
              </div>
            </div>
          ) : (
            <div className="kb-status empty">
              <span className="kb-dot empty-dot" />
              <div className="kb-label">No PDF indexed</div>
            </div>
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            style={{ display: 'none' }}
            onChange={handleUpload}
          />
          <button
            className={`btn-upload ${uploading ? 'uploading' : ''}`}
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? '⏳ Indexing PDF...' : '📄 Upload AU-C Standards PDF'}
          </button>
          {uploading && <p className="upload-note">This may take 1–2 minutes for a large PDF.</p>}
        </div>

        {/* Last run log */}
        {lastAgentMessage?.agent_logs?.length > 0 && (
          <div className="sidebar-logs">
            <div className="nav-label">LAST RUN LOG</div>
            {lastAgentMessage.agent_logs.map((log, i) => (
              <div key={i} className="log-entry">
                <span className="log-agent">{log.agent}</span>
                <span className="log-action">{log.action}</span>
              </div>
            ))}
          </div>
        )}

        <div className="sidebar-footer">
          <button className="btn-clear" onClick={handleClear}>🗑 Clear conversation</button>
          <p className="footer-note">Powered by Claude · AICPA AU-C 2025</p>
        </div>
      </aside>

      {/* ── Main chat ── */}
      <main className="main-area">
        <header className="chat-header">
          <div className="chat-header-title">Audit Knowledge Chat</div>
          <div className="chat-header-sub">
            {kbStatus?.indexed
              ? `RAG active — answers grounded in ${kbStatus.source}`
              : 'Upload the AICPA AU-C PDF in the sidebar to enable RAG'}
          </div>
        </header>

        <ChatWindow messages={messages} isLoading={isLoading} />

        {error && (
          <div className="error-bar">
            ⚠️ {error}
            <button onClick={() => setError(null)}>✕</button>
          </div>
        )}

        <InputBar onSend={handleSend} isLoading={isLoading} />
      </main>
    </div>
  )
}

function AgentBadge({ name, icon, desc, active }) {
  return (
    <div className="agent-badge">
      <div className="agent-badge-icon">{icon}</div>
      <div className="agent-badge-info">
        <div className="agent-badge-name">{name}</div>
        <div className="agent-badge-desc">{desc}</div>
      </div>
      <div className={`agent-status ${active ? 'active' : 'inactive'}`} />
    </div>
  )
}
