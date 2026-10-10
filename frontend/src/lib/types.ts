export type ScanType = 'filesystem' | 'tls'
export type RunStatus = 'queued' | 'running' | 'completed' | 'partial' | 'failed'

export interface DiscoveryRun {
  id: string
  scan_type: ScanType
  trigger_type: 'manual' | 'scheduled'
  status: RunStatus
  created_at: string
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
  record_count: number
  unique_count: number
  error_count: number
  error_summary: string
  status_message: string
  agent_version: string
  evidence_source: 'live' | 'sample'
  config: Record<string, unknown>
}

export interface DistributionPoint {
  label: string
  value: number
}

export interface DashboardData {
  totals: {
    total_runs: number
    active_runs: number
    filesystem_runs: number
    tls_runs: number
    total_evidence: number
  }
  status_counts: DistributionPoint[]
  type_counts: DistributionPoint[]
  trend: Array<{
    date: string
    scan_type: ScanType
    runs: number
    findings: number
    avg_duration_ms: number
  }>
  latest_runs: DiscoveryRun[]
}

export interface HealthData {
  status: string
  components: {
    api: ComponentHealth
    database: ComponentHealth
    agent: ComponentHealth & {
      version?: string
      active_runs?: number
      os?: string
    }
  }
}

export interface ComponentHealth {
  status: string
  message?: string
}

export interface AppConfig {
  default_scan_roots: string[]
  default_tls_duration_seconds: number
  default_probe_targets: string[]
  supported_os: string
  agent_url: string
}

export interface GraphNode {
  id: string
  type: 'host' | 'process' | 'certificate' | 'endpoint' | 'service'
  label: string
  metadata: Record<string, string | number>
}

export interface GraphEdge {
  source: string
  target: string
  type: string
  weight: number
  first_seen: string
  last_seen: string
  evidence: Record<string, string | number>
}

export interface EvidenceGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface CertificateObservation {
  id: number
  path: string
  filename: string
  format: string
  discovered_at: string
  scan_root: string
  fingerprint_sha256: string
  serial_number: string
  subject: string
  issuer: string
  san_entries: string[]
  chain_position: number
  public_key_algorithm: string
  public_key_size: number
  signature_algorithm: string
  valid_from: string | null
  valid_to: string | null
  days_to_expiry: number | null
  validity_status: string
  owner_process: string
  parsing_status: string
  access_error: string
  evidence_confidence: string
  duplicate: boolean
  duplicate_of: string
}

export interface FilesystemReport {
  run: DiscoveryRun
  summary: {
    certificates_found: number
    unique_certificates: number
    valid: number
    expiring: number
    expired: number
    parse_failed: number
    duplicate_observations: number
  }
  distributions: {
    validity: DistributionPoint[]
    algorithms: DistributionPoint[]
    key_sizes: DistributionPoint[]
    issuers: DistributionPoint[]
    locations: DistributionPoint[]
  }
  observations: CertificateObservation[]
  graph: EvidenceGraph
}

export interface TLSObservation {
  id: number
  observed_at: string
  source_ip: string
  source_port: number
  destination_ip: string
  destination_port: number
  direction: string
  transport: string
  connection_state: string
  handshake_outcome: string
  hostname: string
  sni: string
  tls_version: string
  cipher_suite: string
  peer_certificate_fingerprint: string
  peer_certificate_subject: string
  peer_certificate_issuer: string
  peer_certificate_valid_to: string | null
  certificate_status: string
  pid: number
  process_name: string
  executable: string
  local_service: string
  event_count: number
  capture_method: string
  evidence_confidence: string
  error: string
}

export interface TLSReport {
  run: DiscoveryRun
  summary: {
    events_observed: number
    unique_endpoints: number
    unique_ports: number
    certificates_observed: number
    successful_handshakes: number
    errors: number
    mapped_relationships: number
  }
  distributions: {
    tls_versions: DistributionPoint[]
    cipher_suites: DistributionPoint[]
    endpoints: DistributionPoint[]
    certificate_posture: DistributionPoint[]
    activity: DistributionPoint[]
  }
  observations: TLSObservation[]
  graph: EvidenceGraph
}

export interface ScanSchedule {
  id: string
  name: string
  scan_type: ScanType
  interval_minutes: number
  enabled: boolean
  config: Record<string, unknown>
  created_at: string
  updated_at: string
  last_run_at: string | null
  next_run_at: string | null
}

export interface FilesystemScanInput {
  roots: string[]
}

export interface TLSScanInput {
  duration_seconds: number
  probe_targets: string[]
}

export interface ScheduleInput {
  name: string
  scan_type: ScanType
  interval_minutes: number
  enabled: boolean
  filesystem?: FilesystemScanInput
  tls?: TLSScanInput
}