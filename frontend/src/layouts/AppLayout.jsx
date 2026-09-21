import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import HealthBadge from '../components/HealthBadge';

export const AppLayout = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { to: '/dashboard', label: 'Dashboard', icon: '📊' },
    { to: '/sessions', label: 'Gaming Sessions', icon: '🎮' },
    { to: '/memories', label: 'Second Brain', icon: '🧠' },
    { to: '/tasks', label: 'Productivity Tasks', icon: '⚡' },
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
        >
          {mobileMenuOpen ? '✕' : '☰'}
        </button>
      </header>

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
              <span className="nav-label">{item.label}</span>
            </NavLink>
          ))}
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
