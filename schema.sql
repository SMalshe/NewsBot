-- schema.sql — News Bot database schema (plain Postgres).
-- Works as-is on Neon AND Supabase. Run it in the Neon SQL Editor or the
-- Supabase SQL Editor.

-- Who receives briefings, and their preferences.
CREATE TABLE IF NOT EXISTS subscribers (
  phone        TEXT PRIMARY KEY,                 -- E.164, e.g. +16085551234
  topics       TEXT[] NOT NULL DEFAULT '{ai,world}',
  status       TEXT NOT NULL DEFAULT 'active',   -- 'active' | 'stopped'
  consent_at   TIMESTAMPTZ,                      -- when they most recently opted in
  consent_text TEXT,                             -- the language they agreed to
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Immutable audit trail: one row per opt-in / opt-out event.
-- This is the "document" you can show a carrier as proof of consent.
CREATE TABLE IF NOT EXISTS consent_log (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  phone        TEXT NOT NULL,
  event        TEXT NOT NULL,                    -- 'opt_in' | 'opt_out'
  method       TEXT,                             -- 'web_form' | 'sms_keyword'
  consent_text TEXT,                             -- exact language / message
  ip           TEXT,                             -- web sign-ups: requester IP
  user_agent   TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS consent_log_phone_idx ON consent_log (phone);
