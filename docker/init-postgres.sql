-- PostgreSQL initialization script for Reconly
-- This script runs automatically when the PostgreSQL container is first created.
--
-- It enables the required extensions and creates the test database.

-- Enable pgvector extension for vector similarity search (main database)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create test database for running pytest
CREATE DATABASE reconly_test;

-- Connect to test database and enable pgvector
\c reconly_test;
CREATE EXTENSION IF NOT EXISTS vector;

-- Switch back to main database
\c reconly;

-- Verify the extension is installed
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE EXCEPTION 'pgvector extension failed to install';
    END IF;
    RAISE NOTICE 'pgvector extension is ready';
    RAISE NOTICE 'Test database reconly_test created';
END $$;
