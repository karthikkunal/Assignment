# Architecture and evidence model

## Component boundaries

### Endpoint agent (`agent/`)

- A single Windows executable written in Go.
- Binds only to an explicit loopback address.
- Accepts filesystem and TLS metadata commands asynchronously.
- Reports status and final structured evidence to the backend with bounded retries.
- Writes JSON logs locally and shuts down on `Ctrl+C`/termination.

### Local backend (`backend/`)

- FastAPI owns run identifiers and state transitions: `queued`, `running`, `completed`, `partial`, and `failed`.
- Pydantic rejects unknown or malformed agent fields.
- SQLite runs in WAL mode with foreign keys and versioned SQL migrations.
- Result ingestion is idempotent per run: prior evidence is replaced atomically before a callback is committed.
- APScheduler restores enabled interval schedules from SQLite at startup.
- The built React SPA is served from the same loopback origin.

### Browser interface (`frontend/`)

- TanStack Query polls active local evidence and invalidates views after commands.
- Routes map directly to the three assignment views.
- Recharts visualizes distributions and trends; React Flow renders directed, weighted relationships.
- Large visualization libraries are route-split from the initial bundle.

## Command and callback flow

```mermaid
sequenceDiagram
    participant U as Browser
    participant B as Backend API
    participant A as Endpoint agent
    participant D as SQLite

    U->>B: POST /runs/filesystem or /runs/tls
    B->>D: Insert queued run
    B->>A: POST command with run ID
    B-->>U: 202 + run
    A->>B: POST running status
    B->>D: Update run
    A->>A: Collect metadata-only evidence
    A->>B: POST validated result
    B->>D: Atomic observations + graph + completed status
    U->>B: GET report
    B-->>U: Metrics + table + graph
```

## Relationship model

Node identities are stable within a run:

- `host:local`
- `process:<SHA-256(pid:name)>`
- `endpoint:<host-or-ip>:<port>`
- `service:<SHA-256(name:port)>`
- `certificate:<DER SHA-256 fingerprint>`

Directed edge types are `stores`, `owns`, `runs`, `communicates_with`, `provides`, `presents`, and `observes`. Repeated evidence increments `weight` and updates `last_seen` on the existing edge.

## Data model

```mermaid
erDiagram
    RUNS ||--o{ FILESYSTEM_OBSERVATIONS : contains
    RUNS ||--o{ TLS_OBSERVATIONS : contains
    RUNS ||--o{ RELATIONSHIP_NODES : maps
    RUNS ||--o{ RELATIONSHIP_EDGES : maps

    RUNS {
        text id PK
        text scan_type
        text trigger_type
        text status
        text created_at
        integer record_count
        integer error_count
    }
    FILESYSTEM_OBSERVATIONS {
        integer id PK
        text run_id FK
        text path
        text fingerprint_sha256
        text validity_status
        text parsing_status
    }
    TLS_OBSERVATIONS {
        integer id PK
        text run_id FK
        text destination_ip
        integer destination_port
        text tls_version
        text cipher_suite
        integer event_count
    }
    RELATIONSHIP_NODES {
        text run_id PK,FK
        text node_key PK
        text node_type
    }
    RELATIONSHIP_EDGES {
        integer id PK
        text run_id FK
        text source_key
        text target_key
        text edge_type
        integer weight
    }
```

## Security boundaries

- Both listeners default to `127.0.0.1`; the agent refuses non-loopback bind addresses.
- `scripts/start.ps1` creates a fresh in-memory shared token for API-to-agent commands and callbacks unless `QG_AGENT_TOKEN` is supplied.
- HTTP request bodies are size-limited and JSON contracts reject extra fields.
- The filesystem scanner does not follow symlinks and bounds certificate-file reads to 16 MiB.
- Keystore credentials, private keys, TLS payloads, and decrypted content are never requested or retained.
- SQL statements use bound parameters; report grouping expressions are internal constants, not user input.