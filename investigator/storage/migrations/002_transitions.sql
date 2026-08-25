-- Milestone 3: auditable investigation transitions and persisted scope.

CREATE TABLE IF NOT EXISTS investigation_events (
    event_id TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL REFERENCES investigations (investigation_id),
    from_status TEXT,
    to_status TEXT NOT NULL,
    at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS investigation_events_investigation_idx
    ON investigation_events (investigation_id, at);

ALTER TABLE investigations
    ADD COLUMN IF NOT EXISTS scope JSONB,
    ADD COLUMN IF NOT EXISTS notes TEXT;
