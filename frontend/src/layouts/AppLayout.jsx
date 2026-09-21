import React, { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import HealthBadge from '../components/HealthBadge';
import { SECOND_BRAIN_URL } from '../utils/constants';

export const AppLayout = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Close mobile drawer when pressing Escape
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && mobileMenuOpen) {
        setMobileMenuOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [mobileMenuOpen]);

  const handleLogout = () => {
    setMobileMenuOpen(false);
    logout();
    navigate('/login');
  };

  const navItems = [
    { to: '/dashboard', label: 'Dashboard', icon: '📊' },
    { to: '/sessions', label: 'Cyber HUD', icon: '🎮', tag: 'NOW' },
    { to: '/memories', label: 'Second Brain', icon: '🧠', tag: 'BEFORE' },
    { to: '/copilot', label: 'AI Copilot', icon: '🤖', tag: 'NOW+BEFORE' },
    { to: '/tasks', label: 'Productivity', icon: '⚡', tag: 'NEXT' },
  ];

  return (
    <div className="app-container">
      {/* Mobile Header Bar */}
      <header className="mobile-header">
        <div className="brand-logo">
          <span className="logo-symbol">⚔️</span>
          <span className="logo-text">AI Copilot</span>
        </div>
        <button
          className="mobile-menu-toggle"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Toggle navigation menu"
          aria-expanded={mobileMenuOpen}
        >
          {mobileMenuOpen ? '✕' : '☰'}
        </button>
      </header>

      {/* Mobile Backdrop Overlay */}
      {mobileMenuOpen && (
        <div
          className="mobile-nav-backdrop"
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Main Sidebar */}
      <aside className={`app-sidebar ${mobileMenuOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-header">
          <div className="brand-logo">
            <span className="logo-symbol">⚔️</span>
            <div className="brand-info">
              <span className="logo-text">AI Copilot</span>
              <span className="badge-mvp">FOUNDATION</span>
            </div>
          </div>
          <button
            className="mobile-sidebar-close"
            onClick={() => setMobileMenuOpen(false)}
            aria-label="Close navigation menu"
          >
            ✕
          </button>
        </div>

        <div className="sidebar-health">
          <HealthBadge />
        </div>

        <nav className="sidebar-nav">
          <span className="nav-heading">NAVIGATION</span>
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setMobileMenuOpen(false)}
              className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                <span>{item.label}</span>
                {item.tag && (
                  <span style={{
                    fontSize: '0.62rem',
                    fontWeight: 700,
                    letterSpacing: '0.04em',
                    padding: '0.1rem 0.4rem',
                    borderRadius: '4px',
                    background: item.tag === 'NOW' ? 'rgba(56, 189, 248, 0.15)' :
                                item.tag === 'BEFORE' ? 'rgba(168, 85, 247, 0.15)' :
                                item.tag === 'NEXT' ? 'rgba(52, 211, 153, 0.15)' :
                                'rgba(245, 158, 11, 0.15)',
                    color: item.tag === 'NOW' ? '#38bdf8' :
                           item.tag === 'BEFORE' ? '#c084fc' :
                           item.tag === 'NEXT' ? '#34d399' :
                           '#fbbf24'
                  }}>
                    {item.tag}
                  </span>
                )}
              </span>
            </NavLink>
          ))}
          <a
            href={SECOND_BRAIN_URL}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setMobileMenuOpen(false)}
            className="nav-link"
            style={{ color: '#38bdf8', border: '1px dashed rgba(56, 189, 248, 0.4)', marginTop: '0.4rem' }}
            title="Open Python NLP match simulation cockpit"
          >
            <span className="nav-icon">🚀</span>
            <span className="nav-label">Cyber HUD ↗</span>
          </a>
        </nav>

        <div className="sidebar-footer">
          <div className="user-profile">
            <div className="user-avatar">
              {user?.name ? user.name.charAt(0).toUpperCase() : 'U'}
            </div>
            <div className="user-details">
              <span className="user-name">{user?.name || 'Gamer'}</span>
              <span className="user-email">{user?.email || ''}</span>
            </div>
          </div>
          <button className="btn-logout" onClick={handleLogout} title="Sign Out">
            <span className="logout-icon">⎋</span>
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="app-main">
        <div className="main-content-scroll">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default AppLayout;
