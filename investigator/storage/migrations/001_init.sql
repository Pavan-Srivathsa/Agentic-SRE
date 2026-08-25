-- Investigator database schema (Milestone 2).
-- Application writes only come from fault injection in this pass.

CREATE TABLE IF NOT EXISTS deployments (
    deployment_id TEXT PRIMARY KEY,
    service TEXT NOT NULL,
    version TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    deployed_at TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS deployments_service_time_idx
    ON deployments (service, deployed_at DESC);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    alert_id TEXT,
    service TEXT,
    severity TEXT,
    started_at TIMESTAMPTZ,
    status TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    alert_name TEXT,
    service TEXT,
    severity TEXT,
    starts_at TIMESTAMPTZ,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS investigations (
    investigation_id TEXT PRIMARY KEY,
    incident_id TEXT,
    status TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tool_calls (
    tool_call_id TEXT PRIMARY KEY,
    investigation_id TEXT,
    tool TEXT,
    arguments JSONB,
    started_at TIMESTAMPTZ,
    duration_ms DOUBLE PRECISION,
    ok BOOLEAN
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    investigation_id TEXT,
    source TEXT,
    service TEXT,
    timestamp_start TIMESTAMPTZ,
    timestamp_end TIMESTAMPTZ,
    observation TEXT,
    raw_reference TEXT,
    supports TEXT[] DEFAULT '{}',
    contradicts TEXT[] DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS hypotheses (
    hypothesis_id TEXT PRIMARY KEY,
    investigation_id TEXT,
    title TEXT,
    description TEXT,
    affected_service TEXT,
    confidence DOUBLE PRECISION,
    status TEXT
);

CREATE TABLE IF NOT EXISTS timeline_events (
    event_id TEXT PRIMARY KEY,
    investigation_id TEXT,
    occurred_at TIMESTAMPTZ,
    summary TEXT,
    evidence_id TEXT
);

CREATE TABLE IF NOT EXISTS reports (
    report_id TEXT PRIMARY KEY,
    investigation_id TEXT,
    body TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evaluations (
    evaluation_id TEXT PRIMARY KEY,
    scenario_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS service_dependencies (
    service TEXT NOT NULL,
    dependency TEXT NOT NULL,
    PRIMARY KEY (service, dependency)
);
