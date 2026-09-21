import React, { useState, useRef, useEffect, useCallback } from 'react';
import api from '../services/api';

const SUGGESTED_QUESTIONS = [
  'When did I perform best?',
  'What was my last session?',
  'How much have I gamed?',
  'What tasks are pending?'
];

const ACTIVE_CONVO_STORAGE_KEY = 'copilot_active_conversation_id';

export const Copilot = () => {
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(() => {
    return localStorage.getItem(ACTIVE_CONVO_STORAGE_KEY) || null;
  });
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [lastFailedMessage, setLastFailedMessage] = useState(null);

  const chatBottomRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom whenever messages or loading state change
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading, isLoadingMessages]);

  // Load user conversations
  const loadConversations = useCallback(async () => {
    try {
      setIsLoadingConversations(true);
      const res = await api.getConversations({ limit: 50 });
      if (res && res.success && res.data) {
        setConversations(res.data.conversations || []);
      }
    } catch (err) {
      console.error('Failed to load conversations:', err);
    } finally {
      setIsLoadingConversations(false);
    }
  }, []);

  // Load specific conversation messages
  const loadConversationMessages = useCallback(async (conversationId) => {
    if (!conversationId) {
      setMessages([]);
      return;
    }

    try {
      setIsLoadingMessages(true);
      const res = await api.getConversation(conversationId);
      if (res && res.success && res.data?.conversation) {
        const rawMessages = res.data.conversation.messages || [];
        const formatted = rawMessages.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          insights: Array.isArray(m.sources?.insights) ? m.sources.insights : [],
          sources: m.sources || null,
          provider: m.provider || 'development',
          timestamp: new Date(m.createdAt)
        }));
        setMessages(formatted);
      }
    } catch (err) {
      console.error('Failed to load conversation messages:', err);
      // If conversation was deleted or not found, reset
      if (err.status === 404) {
        setActiveConversationId(null);
        localStorage.removeItem(ACTIVE_CONVO_STORAGE_KEY);
        setMessages([]);
      }
    } finally {
      setIsLoadingMessages(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadConversations();
    if (activeConversationId) {
      loadConversationMessages(activeConversationId);
    }
  }, [loadConversations, loadConversationMessages, activeConversationId]);

  // Select a conversation from history
  const handleSelectConversation = (id) => {
    if (id === activeConversationId) return;
    setActiveConversationId(id);
    localStorage.setItem(ACTIVE_CONVO_STORAGE_KEY, id);
    setIsSidebarOpen(false);
  };

  // Start a new chat
  const handleStartNewChat = () => {
    setActiveConversationId(null);
    localStorage.removeItem(ACTIVE_CONVO_STORAGE_KEY);
    setMessages([]);
    setInputValue('');
    setLastFailedMessage(null);
    setIsSidebarOpen(false);
    inputRef.current?.focus();
  };

  // Delete a conversation
  const handleDeleteConversation = async (id, e) => {
    if (e) e.stopPropagation();
    try {
      await api.deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeConversationId === id) {
        handleStartNewChat();
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  };

  // Send chat message
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
      const response = await api.sendChatMessage(textToSend, activeConversationId);

      if (response && response.success && response.data) {
        const { conversationId, message, insights, sources, provider } = response.data;

        // If a new conversation was created on the backend, store it
        if (conversationId && conversationId !== activeConversationId) {
          setActiveConversationId(conversationId);
          localStorage.setItem(ACTIVE_CONVO_STORAGE_KEY, conversationId);
          loadConversations();
        }

        const assistantMessage = {
          id: `bot-${Date.now()}`,
          role: 'assistant',
          content: message || 'I have reviewed your Second Brain context.',
          insights: Array.isArray(insights) ? insights : [],
          sources: sources || null,
          provider: provider || 'development',
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

  const formatConvoDate = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric'
    });
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
        <div className="copilot-header-actions">
          <button
            className="mobile-history-toggle"
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            title="Toggle Conversation History"
          >
            💬 History {conversations.length > 0 && `(${conversations.length})`}
          </button>
          <div className="copilot-badge">
            <span className="copilot-mode-dot"></span>
            <span>Second Brain Connected</span>
          </div>
        </div>
      </div>

      {/* Main Copilot Body with Persistent History Sidebar */}
      <div className="copilot-workspace-layout">
        {/* Responsive Overlay Backdrop */}
        {isSidebarOpen && (
          <div
            className="sidebar-backdrop"
            onClick={() => setIsSidebarOpen(false)}
          />
        )}

        {/* Conversation History Sidebar */}
        <aside className={`copilot-history-sidebar ${isSidebarOpen ? 'sidebar-open' : ''}`}>
          <div className="sidebar-top-action">
            <button
              className="btn-new-chat"
              onClick={handleStartNewChat}
              title="Start a new conversation"
            >
              <span className="new-chat-plus">＋</span>
              <span className="new-chat-text">NEW CHAT</span>
            </button>
          </div>

          <div className="history-list-header">
            <span className="history-heading">Previous Conversations</span>
            {conversations.length > 0 && (
              <span className="history-count-badge">{conversations.length}</span>
            )}
          </div>

          <div className="conversations-scroll-area">
            {isLoadingConversations ? (
              <div className="history-loading-indicator">
                <span className="dot"></span>
                <span>Loading chats...</span>
              </div>
            ) : conversations.length === 0 ? (
              <div className="history-empty-message">
                <p>No previous conversations.</p>
                <span>Ask a question to start your first chat!</span>
              </div>
            ) : (
              <div className="conversations-list">
                {conversations.map((convo) => {
                  const isActive = convo.id === activeConversationId;
                  return (
                    <div
                      key={convo.id}
                      className={`conversation-item ${isActive ? 'conversation-active' : ''}`}
                      onClick={() => handleSelectConversation(convo.id)}
                    >
                      <div className="conversation-item-main">
                        <span className="convo-icon">💬</span>
                        <div className="convo-meta">
                          <span className="convo-title" title={convo.title}>
                            {convo.title}
                          </span>
                          <span className="convo-timestamp">
                            {formatConvoDate(convo.updatedAt)}
                          </span>
                        </div>
                      </div>
                      <button
                        type="button"
                        className="convo-delete-btn"
                        title="Delete conversation"
                        onClick={(e) => handleDeleteConversation(convo.id, e)}
                      >
                        ✕
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </aside>

        {/* Main Chat Interface */}
        <div className="copilot-chat-card">
          <div className="copilot-chat-messages">
            {isLoadingMessages ? (
              <div className="loading-container">
                <div className="spinner"></div>
                <span>Restoring conversation history...</span>
              </div>
            ) : messages.length === 0 ? (
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
                        {msg.role === 'user' ? (
                          'You'
                        ) : (
                          <div className="bubble-author-row">
                            <span>Copilot</span>
                            {msg.provider === 'gemini' && (
                              <span className="provider-badge-gemini" title="Verified Gemini AI response">
                                ✨ Powered by Gemini
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                      <div className="bubble-content">
                        {msg.content.split('\n').map((line, i) => (
                          <p key={i} className="bubble-line">
                            {line}
                          </p>
                        ))}
                      </div>

                      {msg.insights && msg.insights.length > 0 && (
                        <div className="copilot-insights">
                          <span className="insights-label">💡 Key Insights:</span>
                          <ul className="insights-list">
                            {msg.insights.map((insight, idx) => (
                              <li key={idx} className="insight-item">{insight}</li>
                            ))}
                          </ul>
                        </div>
                      )}

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
    </div>
  );
};

export default Copilot;
