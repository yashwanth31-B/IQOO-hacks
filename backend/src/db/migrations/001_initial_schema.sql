-- 001_initial_schema.sql
-- Initial database schema for AI Gaming Copilot + Gaming Second Brain

-- Enable pgcrypto for UUID generation (gen_random_uuid is built-in in PostgreSQL 13+)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 1. USERS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 2. GAMES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS games (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    platform VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 3. GAMING SESSIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS gaming_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMPTZ,
    duration INTEGER,
    score NUMERIC,
    performance VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_session_dates CHECK (ended_at IS NULL OR ended_at >= started_at)
);

-- ============================================================================
-- 4. GAMING MEMORIES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS gaming_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES gaming_sessions(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    summary TEXT,
    memory_type VARCHAR(100) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 5. TASKS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    priority VARCHAR(50) DEFAULT 'medium',
    due_date TIMESTAMPTZ,
    estimated_minutes INTEGER,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- INDEXES
-- ============================================================================
-- users
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- gaming_sessions
CREATE INDEX IF NOT EXISTS idx_gaming_sessions_user_id ON gaming_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_gaming_sessions_game_id ON gaming_sessions(game_id);
CREATE INDEX IF NOT EXISTS idx_gaming_sessions_started_at ON gaming_sessions(started_at);

-- gaming_memories
CREATE INDEX IF NOT EXISTS idx_gaming_memories_user_id ON gaming_memories(user_id);
CREATE INDEX IF NOT EXISTS idx_gaming_memories_session_id ON gaming_memories(session_id);
CREATE INDEX IF NOT EXISTS idx_gaming_memories_created_at ON gaming_memories(created_at);

-- tasks
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(completed);
