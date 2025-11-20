-- Database schema for Pepper with DBOS
-- YAGNI: Only essential tables

-- Conversations (DBOS state storage)
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(255) NOT NULL,
    messages JSONB NOT NULL,
    summary TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_agent_created (agent_id, created_at DESC)
);

-- User profiles
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id VARCHAR(255) PRIMARY KEY,
    profile_data JSONB NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Task assignments and tracking
CREATE TABLE IF NOT EXISTS tasks (
    task_id VARCHAR(255) PRIMARY KEY,
    task_type VARCHAR(100) NOT NULL,
    task_data JSONB NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_created (created_at DESC)
);

-- DBOS workflow state (managed by DBOS library)
-- DBOS will create its own tables for workflow execution state
-- No need to manually create them (YAGNI)
