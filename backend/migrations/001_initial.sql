CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    scan_type TEXT NOT NULL CHECK (scan_type IN ('filesystem', 'tls')),
    trigger_type TEXT NOT NULL CHECK (trigger_type IN ('manual', 'scheduled')),
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'partial', 'failed')),
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    duration_ms INTEGER,
    record_count INTEGER NOT NULL DEFAULT 0,
    unique_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    error_summary TEXT NOT NULL DEFAULT '',
    status_message TEXT NOT NULL DEFAULT '',
    config_json TEXT NOT NULL DEFAULT '{}',
    agent_version TEXT NOT NULL DEFAULT '',
    evidence_source TEXT NOT NULL DEFAULT 'live'
);

CREATE INDEX idx_runs_created_at ON runs(created_at DESC);
CREATE INDEX idx_runs_type_status ON runs(scan_type, status);

CREATE TABLE filesystem_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    filename TEXT NOT NULL,
    format TEXT NOT NULL,
    discovered_at TEXT NOT NULL,
    scan_root TEXT NOT NULL,
    fingerprint_sha256 TEXT NOT NULL DEFAULT '',
    serial_number TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    issuer TEXT NOT NULL DEFAULT '',
    san_json TEXT NOT NULL DEFAULT '[]',
    chain_position INTEGER NOT NULL DEFAULT 0,
    public_key_algorithm TEXT NOT NULL DEFAULT '',
    public_key_size INTEGER NOT NULL DEFAULT 0,
    signature_algorithm TEXT NOT NULL DEFAULT '',
    valid_from TEXT,
    valid_to TEXT,
    days_to_expiry INTEGER,
    validity_status TEXT NOT NULL,
    owner_process TEXT NOT NULL DEFAULT 'unavailable',
    parsing_status TEXT NOT NULL,
    access_error TEXT NOT NULL DEFAULT '',
    evidence_confidence TEXT NOT NULL,
    duplicate INTEGER NOT NULL DEFAULT 0,
    duplicate_of TEXT NOT NULL DEFAULT ''
);

CREATE INDEX idx_filesystem_run ON filesystem_observations(run_id);
CREATE INDEX idx_filesystem_fingerprint ON filesystem_observations(fingerprint_sha256);
CREATE INDEX idx_filesystem_validity ON filesystem_observations(run_id, validity_status);

CREATE TABLE tls_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    observed_at TEXT NOT NULL,
    source_ip TEXT NOT NULL DEFAULT '',
    source_port INTEGER NOT NULL DEFAULT 0,
    destination_ip TEXT NOT NULL DEFAULT '',
    destination_port INTEGER NOT NULL DEFAULT 0,
    direction TEXT NOT NULL,
    transport TEXT NOT NULL,
    connection_state TEXT NOT NULL,
    handshake_outcome TEXT NOT NULL,
    hostname TEXT NOT NULL DEFAULT '',
    sni TEXT NOT NULL DEFAULT '',
    tls_version TEXT NOT NULL DEFAULT '',
    cipher_suite TEXT NOT NULL DEFAULT '',
    peer_certificate_fingerprint TEXT NOT NULL DEFAULT '',
    peer_certificate_subject TEXT NOT NULL DEFAULT '',
    peer_certificate_issuer TEXT NOT NULL DEFAULT '',
    peer_certificate_valid_to TEXT,
    certificate_status TEXT NOT NULL DEFAULT '',
    pid INTEGER NOT NULL DEFAULT 0,
    process_name TEXT NOT NULL DEFAULT '',
    executable TEXT NOT NULL DEFAULT '',
    local_service TEXT NOT NULL DEFAULT '',
    event_count INTEGER NOT NULL DEFAULT 1,
    capture_method TEXT NOT NULL,
    evidence_confidence TEXT NOT NULL,
    error TEXT NOT NULL DEFAULT ''
);

CREATE INDEX idx_tls_run ON tls_observations(run_id);
CREATE INDEX idx_tls_endpoint ON tls_observations(run_id, destination_ip, destination_port);
CREATE INDEX idx_tls_version ON tls_observations(run_id, tls_version);

CREATE TABLE relationship_nodes (
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    node_key TEXT NOT NULL,
    node_type TEXT NOT NULL CHECK (node_type IN ('host', 'process', 'certificate', 'endpoint', 'service')),
    label TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (run_id, node_key)
);

CREATE TABLE relationship_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    source_key TEXT NOT NULL,
    target_key TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    weight INTEGER NOT NULL DEFAULT 1,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (run_id, source_key, target_key, edge_type),
    FOREIGN KEY (run_id, source_key) REFERENCES relationship_nodes(run_id, node_key) ON DELETE CASCADE,
    FOREIGN KEY (run_id, target_key) REFERENCES relationship_nodes(run_id, node_key) ON DELETE CASCADE
);

CREATE INDEX idx_edges_run ON relationship_edges(run_id);

CREATE TABLE schedules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    scan_type TEXT NOT NULL CHECK (scan_type IN ('filesystem', 'tls')),
    interval_minutes INTEGER NOT NULL CHECK (interval_minutes BETWEEN 1 AND 10080),
    enabled INTEGER NOT NULL DEFAULT 1,
    config_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_run_at TEXT,
    next_run_at TEXT
);

CREATE INDEX idx_schedules_enabled ON schedules(enabled, scan_type);