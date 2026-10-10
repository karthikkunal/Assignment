package model

import "time"

type ScanError struct {
	Path    string `json:"path,omitempty"`
	Message string `json:"message"`
}

type FilesystemScanRequest struct {
	RunID string   `json:"run_id"`
	Roots []string `json:"roots"`
}

type TLSScanRequest struct {
	RunID           string   `json:"run_id"`
	DurationSeconds int      `json:"duration_seconds"`
	ProbeTargets    []string `json:"probe_targets"`
}

type StatusUpdate struct {
	Status    string    `json:"status"`
	Timestamp time.Time `json:"timestamp"`
	Message   string    `json:"message,omitempty"`
}

type CertificateObservation struct {
	Path               string     `json:"path"`
	Filename           string     `json:"filename"`
	Format             string     `json:"format"`
	DiscoveredAt       time.Time  `json:"discovered_at"`
	ScanRoot           string     `json:"scan_root"`
	FingerprintSHA256  string     `json:"fingerprint_sha256,omitempty"`
	SerialNumber       string     `json:"serial_number,omitempty"`
	Subject            string     `json:"subject,omitempty"`
	Issuer             string     `json:"issuer,omitempty"`
	SANEntries         []string   `json:"san_entries"`
	ChainPosition      int        `json:"chain_position"`
	PublicKeyAlgorithm string     `json:"public_key_algorithm,omitempty"`
	PublicKeySize      int        `json:"public_key_size,omitempty"`
	SignatureAlgorithm string     `json:"signature_algorithm,omitempty"`
	ValidFrom          *time.Time `json:"valid_from,omitempty"`
	ValidTo            *time.Time `json:"valid_to,omitempty"`
	DaysToExpiry       *int       `json:"days_to_expiry,omitempty"`
	ValidityStatus     string     `json:"validity_status"`
	OwnerProcess       string     `json:"owner_process"`
	ParsingStatus      string     `json:"parsing_status"`
	AccessError        string     `json:"access_error,omitempty"`
	EvidenceConfidence string     `json:"evidence_confidence"`
	Duplicate          bool       `json:"duplicate"`
	DuplicateOf        string     `json:"duplicate_of,omitempty"`
}

type FilesystemScanResult struct {
	RunID        string                   `json:"run_id"`
	Status       string                   `json:"status"`
	StartedAt    time.Time                `json:"started_at"`
	CompletedAt  time.Time                `json:"completed_at"`
	AgentVersion string                   `json:"agent_version"`
	Observations []CertificateObservation `json:"observations"`
	Errors       []ScanError              `json:"errors"`
}

type TLSObservation struct {
	ObservedAt                 time.Time  `json:"observed_at"`
	SourceIP                   string     `json:"source_ip,omitempty"`
	SourcePort                 int        `json:"source_port,omitempty"`
	DestinationIP              string     `json:"destination_ip,omitempty"`
	DestinationPort            int        `json:"destination_port,omitempty"`
	Direction                  string     `json:"direction"`
	Transport                  string     `json:"transport"`
	ConnectionState            string     `json:"connection_state"`
	HandshakeOutcome           string     `json:"handshake_outcome"`
	Hostname                   string     `json:"hostname,omitempty"`
	SNI                        string     `json:"sni,omitempty"`
	TLSVersion                 string     `json:"tls_version,omitempty"`
	CipherSuite                string     `json:"cipher_suite,omitempty"`
	PeerCertificateFingerprint string     `json:"peer_certificate_fingerprint,omitempty"`
	PeerCertificateSubject     string     `json:"peer_certificate_subject,omitempty"`
	PeerCertificateIssuer      string     `json:"peer_certificate_issuer,omitempty"`
	PeerCertificateValidTo     *time.Time `json:"peer_certificate_valid_to,omitempty"`
	CertificateStatus          string     `json:"certificate_status,omitempty"`
	PID                        int        `json:"pid,omitempty"`
	ProcessName                string     `json:"process_name,omitempty"`
	Executable                 string     `json:"executable,omitempty"`
	LocalService               string     `json:"local_service,omitempty"`
	EventCount                 int        `json:"event_count"`
	CaptureMethod              string     `json:"capture_method"`
	EvidenceConfidence         string     `json:"evidence_confidence"`
	Error                      string     `json:"error,omitempty"`
}

type TLSScanResult struct {
	RunID        string           `json:"run_id"`
	Status       string           `json:"status"`
	StartedAt    time.Time        `json:"started_at"`
	CompletedAt  time.Time        `json:"completed_at"`
	AgentVersion string           `json:"agent_version"`
	Observations []TLSObservation `json:"observations"`
	Errors       []ScanError      `json:"errors"`
}
