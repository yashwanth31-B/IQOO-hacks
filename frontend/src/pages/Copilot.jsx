import React, { useState, useRef, useEffect } from 'react';
import api from '../services/api';

const SUGGESTED_QUESTIONS = [
  'When did I perform best?',
  'What was my last session?',
  'How much have I gamed?',
  'What tasks are pending?'
];

export const Copilot = () => {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [lastFailedMessage, setLastFailedMessage] = useState(null);
  const chatBottomRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom whenever messages or loading state change
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSendMessage = async (rawMessage) => {
    const textToSend = (rawMessage || inputValue || '').trim();
    if (!textToSend || isLoading) return;

    // Append user message immediately
    const userMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: textToSend,
      timestamp: new Date()
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);
    setLastFailedMessage(null);

    try {
      const response = await api.post('/ai/chat', { message: textToSend });

      if (response && response.success && response.data) {
        const assistantMessage = {
          id: `bot-${Date.now()}`,
          role: 'assistant',
          content: response.data.message || 'I have reviewed your Second Brain context.',
          sources: response.data.sources || null,
          provider: response.data.provider || 'development',
          timestamp: new Date()
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } else {
        throw new Error('Invalid response structure from Copilot API');
      }
    } catch (err) {
      setLastFailedMessage(textToSend);
      const errorMessage = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: "I couldn't process that request right now.",
        isError: true,
        timestamp: new Date()
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleRetry = () => {
    if (lastFailedMessage) {
      handleSendMessage(lastFailedMessage);
    }
  };

  const renderSources = (sources) => {
    if (!sources) return null;
    const sessionCount = sources.sessions?.length || 0;
    const memoryCount = sources.memories?.length || 0;
    const taskCount = sources.tasks?.length || 0;

    if (sessionCount === 0 && memoryCount === 0 && taskCount === 0) {
      return null;
    }

    return (
      <div className="copilot-sources">
        <span className="sources-label">Second Brain Sources:</span>
        <div className="sources-tags">
          {sessionCount > 0 && (
            <span className="source-tag session-tag" title="Gaming Sessions queried">
              🎮 {sessionCount} {sessionCount === 1 ? 'session' : 'sessions'}
            </span>
          )}
          {memoryCount > 0 && (
            <span className="source-tag memory-tag" title="Second Brain Memories queried">
              🧠 {memoryCount} {memoryCount === 1 ? 'memory' : 'memories'}
            </span>
          )}
          {taskCount > 0 && (
            <span className="source-tag task-tag" title="Productivity Tasks queried">
              ⚡ {taskCount} {taskCount === 1 ? 'task' : 'tasks'}
            </span>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="page-container copilot-page-container">
      {/* Header */}
      <div className="page-header copilot-header">
        <div>
          <div className="copilot-title-row">
            <span className="copilot-icon">🤖</span>
            <h1 className="page-title">AI Gaming Copilot</h1>
          </div>
          <p className="page-subtitle">Your intelligent gaming assistant & Second Brain companion</p>
        </div>
        <div className="copilot-badge">
          <span className="copilot-mode-dot"></span>
          <span>Second Brain Connected</span>
        </div>
      </div>

      {/* Main Chat Interface */}
      <div className="copilot-chat-card">
        <div className="copilot-chat-messages">
          {messages.length === 0 ? (
            <div className="copilot-empty-state">
              <div className="empty-icon-bubble">🤖</div>
              <h2 className="empty-title">AI GAMING COPILOT</h2>
              <p className="empty-description">
                Your gaming journey has a memory. Ask me about your performance, previous sessions, 
                key moments, and upcoming productivity tasks.
              </p>

              <div className="suggested-questions-section">
                <span className="suggested-heading">Suggested Inquiries</span>
                <div className="suggested-buttons-grid">
                  {SUGGESTED_QUESTIONS.map((q, idx) => (
                    <button
                      key={idx}
                      className="suggested-btn"
                      onClick={() => handleSendMessage(q)}
                      disabled={isLoading}
                    >
                      <span className="suggested-icon">💬</span>
                      <span className="suggested-text">{q}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="messages-stream">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`chat-bubble-row ${msg.role === 'user' ? 'row-user' : 'row-assistant'}`}
                >
                  <div className="bubble-avatar">
                    {msg.role === 'user' ? '👤' : '🤖'}
                  </div>
                  <div className={`chat-bubble ${msg.role === 'user' ? 'bubble-user' : 'bubble-assistant'} ${msg.isError ? 'bubble-error' : ''}`}>
                    <div className="bubble-author">
                      {msg.role === 'user' ? 'You' : 'Copilot'}
                    </div>
                    <div className="bubble-content">
                      {msg.content.split('\n').map((line, i) => (
                        <p key={i} className="bubble-line">
                          {line}
                        </p>
                      ))}
                    </div>

                    {msg.sources && renderSources(msg.sources)}

                    {msg.isError && (
                      <div className="error-retry-action">
                        <button className="btn-retry" onClick={handleRetry} disabled={isLoading}>
                          ↺ Try Again
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="chat-bubble-row row-assistant">
                  <div className="bubble-avatar">🤖</div>
                  <div className="chat-bubble bubble-assistant bubble-thinking">
                    <div className="thinking-dots">
                      <span className="dot"></span>
                      <span className="dot"></span>
                      <span className="dot"></span>
                    </div>
                    <span className="thinking-text">Copilot is thinking...</span>
                  </div>
                </div>
              )}

              <div ref={chatBottomRef} />
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div className="copilot-input-container">
          <form
            className="copilot-input-form"
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
          >
            <input
              ref={inputRef}
              type="text"
              className="copilot-text-input"
              placeholder="Ask about your gaming journey..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              maxLength={2000}
            />
            <button
              type="submit"
              className="btn-primary copilot-send-btn"
              disabled={isLoading || inputValue.trim().length === 0}
            >
              {isLoading ? 'Thinking...' : 'Send ➔'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default Copilot;
