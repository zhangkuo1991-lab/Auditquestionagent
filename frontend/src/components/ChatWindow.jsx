import { useEffect, useRef } from 'react'
import MessageBubble from './MessageBubble'
import './ChatWindow.css'

export default function ChatWindow({ messages, isLoading }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  return (
    <div className="chat-window">
      <div className="chat-messages">
        {messages.map(msg => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {isLoading && <TypingIndicator />}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="message-row assistant">
      <div className="avatar agent-avatar">🧠</div>
      <div className="bubble agent-bubble typing-bubble">
        <div className="typing-dots">
          <span /><span /><span />
        </div>
        <span className="typing-label">Agents thinking...</span>
      </div>
    </div>
  )
}
