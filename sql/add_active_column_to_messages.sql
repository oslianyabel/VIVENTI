-- Migration: add 'active' column to messages table
-- The schema.py defines this column but it was missing from the existing table.
-- Safe to run multiple times (IF NOT EXISTS).

ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;
