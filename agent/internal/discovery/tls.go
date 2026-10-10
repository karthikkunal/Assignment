package discovery

import (
	"context"
	"crypto/sha256"
	"crypto/tls"
	"encoding/hex"
	"fmt"
	"net"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/quantumgenie/discovery-agent/internal/model"
)

var defaultTLSPorts = map[int]string{
	443:  "HTTPS",
	465:  "SMTPS",
	636:  "LDAPS",
	853:  "DNS over TLS",
	993:  "IMAPS",
	995:  "POP3S",
	8443: "HTTPS alternate",
	8883: "MQTTS",
	9443: "HTTPS alternate",
}

type TCPConnection struct {
	LocalIP    string
	LocalPort  int
	RemoteIP   string
	RemotePort int
	PID        int
	Executable string
}

type TLSScanner struct {
	PollInterval time.Duration
	DialTimeout  time.Duration
	Now          func() time.Time
}

func NewTLSScanner() *TLSScanner {
	return &TLSScanner{
		PollInterval: 500 * time.Millisecond,
		DialTimeout:  5 * time.Second,
		Now:          time.Now,
	}
}

func (scanner *TLSScanner) Scan(ctx context.Context, duration time.Duration, probeTargets []string) ([]model.TLSObservation, []model.ScanError) {
	if duration < time.Second {
		duration = time.Second
	}
	if duration > 5*time.Minute {
		duration = 5 * time.Minute
	}
	pollInterval := scanner.PollInterval
	if pollInterval <= 0 {
		pollInterval = 500 * time.Millisecond
	}

	scanContext, cancel := context.WithTimeout(ctx, duration)
	defer cancel()

	probeResults := make(chan model.TLSObservation, len(probeTargets))
	var probeGroup sync.WaitGroup
	for _, target := range normalizeProbeTargets(probeTargets) {
		probeGroup.Add(1)
		go func(target string) {
			defer probeGroup.Done()
			probeResults <- scanner.ProbeTarget(scanContext, target)
		}(target)
	}
	go func() {
		probeGroup.Wait()
		close(probeResults)
	}()

	observedConnections := make(map[string]model.TLSObservation)
	scanErrors := make([]model.ScanError, 0)
	reportedInventoryError := false
	ticker := time.NewTicker(pollInterval)
	defer ticker.Stop()

	collectConnections := func() {
		connections, err := listTCPConnections()
		if err != nil {
			if !reportedInventoryError {
				scanErrors = append(scanErrors, model.ScanError{Message: fmt.Sprintf("collect Windows TCP ownership table: %v", err)})
				reportedInventoryError = true
			}
			return
		}
		for _, connection := range connections {
			if !isTLSCandidate(connection) {
				continue
			}
			key := connectionKey(connection)
			observation, exists := observedConnections[key]
			if !exists {
				observation = connectionObservation(connection, scanner.Now().UTC())
			}
			observation.EventCount++
			observedConnections[key] = observation
		}
	}

	collectConnections()
	for {
		select {
		case <-scanContext.Done():
			observations := make([]model.TLSObservation, 0, len(observedConnections)+len(probeTargets))
			for _, observation := range observedConnections {
				observations = append(observations, observation)
			}
			for probe := range probeResults {
				observations = append(observations, probe)
			}
			sort.Slice(observations, func(left, right int) bool {
				return observations[left].ObservedAt.Before(observations[right].ObservedAt)
			})
			return observations, scanErrors
		case <-ticker.C:
			collectConnections()
		}
	}
}

func (scanner *TLSScanner) ProbeTarget(ctx context.Context, target string) model.TLSObservation {
	observedAt := scanner.Now().UTC()
	host, port, normalizedTarget, err := parseProbeTarget(target)
	observation := model.TLSObservation{
		ObservedAt:         observedAt,
		DestinationPort:    port,
		Direction:          "outbound",
		Transport:          "TCP",
		ConnectionState:    "attempted",
		HandshakeOutcome:   "failed",
		Hostname:           host,
		EventCount:         1,
		CaptureMethod:      "active_metadata_probe",
		EvidenceConfidence: "low",
	}
	if err != nil {
		observation.Error = err.Error()
		return observation
	}
	if net.ParseIP(host) == nil {
		observation.SNI = host
	}

	dialTimeout := scanner.DialTimeout
	if dialTimeout <= 0 {
		dialTimeout = 5 * time.Second
	}
	dialer := &net.Dialer{Timeout: dialTimeout}
	tlsConfig := &tls.Config{
		InsecureSkipVerify: true,
		MinVersion:         tls.VersionTLS10,
		ServerName:         observation.SNI,
	}
	connection, err := tls.DialWithDialer(dialer, "tcp", normalizedTarget, tlsConfig)
	if err != nil {
		observation.Error = err.Error()
		return observation
	}
	defer connection.Close()

	if localAddress, ok := connection.LocalAddr().(*net.TCPAddr); ok {
		observation.SourceIP = localAddress.IP.String()
		observation.SourcePort = localAddress.Port
	}
	if remoteAddress, ok := connection.RemoteAddr().(*net.TCPAddr); ok {
		observation.DestinationIP = remoteAddress.IP.String()
		observation.DestinationPort = remoteAddress.Port
	}

	state := connection.ConnectionState()
	observation.ConnectionState = "connected"
	observation.HandshakeOutcome = "succeeded"
	observation.TLSVersion = tlsVersionName(state.Version)
	observation.CipherSuite = tls.CipherSuiteName(state.CipherSuite)
	observation.PID = os.Getpid()
	observation.Executable, _ = os.Executable()
	observation.ProcessName = filepath.Base(observation.Executable)
	observation.LocalService = defaultTLSPorts[observation.DestinationPort]
	observation.EvidenceConfidence = "high"

	if len(state.PeerCertificates) > 0 {
		peerCertificate := state.PeerCertificates[0]
		fingerprint := sha256.Sum256(peerCertificate.Raw)
		validTo := peerCertificate.NotAfter.UTC()
		observation.PeerCertificateFingerprint = strings.ToUpper(hex.EncodeToString(fingerprint[:]))
		observation.PeerCertificateSubject = peerCertificate.Subject.String()
		observation.PeerCertificateIssuer = peerCertificate.Issuer.String()
		observation.PeerCertificateValidTo = &validTo
		observation.CertificateStatus = certificateValidityStatus(peerCertificate, observedAt, 30)
	}
	return observation
}

func connectionObservation(connection TCPConnection, observedAt time.Time) model.TLSObservation {
	direction := "outbound"
	servicePort := connection.RemotePort
	sourceIP := connection.LocalIP
	sourcePort := connection.LocalPort
	destinationIP := connection.RemoteIP
	destinationPort := connection.RemotePort
	if _, localIsTLS := defaultTLSPorts[connection.LocalPort]; localIsTLS {
		if _, remoteIsTLS := defaultTLSPorts[connection.RemotePort]; !remoteIsTLS {
			direction = "inbound"
			servicePort = connection.LocalPort
			sourceIP = connection.RemoteIP
			sourcePort = connection.RemotePort
			destinationIP = connection.LocalIP
			destinationPort = connection.LocalPort
		}
	}

	return model.TLSObservation{
		ObservedAt:         observedAt,
		SourceIP:           sourceIP,
		SourcePort:         sourcePort,
		DestinationIP:      destinationIP,
		DestinationPort:    destinationPort,
		Direction:          direction,
		Transport:          "TCP",
		ConnectionState:    "established",
		HandshakeOutcome:   "not_visible_in_tcp_table",
		PID:                connection.PID,
		ProcessName:        filepath.Base(connection.Executable),
		Executable:         connection.Executable,
		LocalService:       defaultTLSPorts[servicePort],
		CaptureMethod:      "windows_ip_helper_api",
		EvidenceConfidence: "medium",
	}
}

func parseProbeTarget(target string) (string, int, string, error) {
	target = strings.TrimSpace(target)
	if target == "" {
		return "", 0, "", fmt.Errorf("probe target is empty")
	}
	if strings.Contains(target, "://") {
		parsed, err := url.Parse(target)
		if err != nil {
			return "", 0, "", fmt.Errorf("parse probe target: %w", err)
		}
		target = parsed.Host
	}
	if !strings.Contains(target, ":") {
		target = net.JoinHostPort(target, "443")
	}
	host, portText, err := net.SplitHostPort(target)
	if err != nil {
		return "", 0, "", fmt.Errorf("probe target must be host:port: %w", err)
	}
	port, err := strconv.Atoi(portText)
	if err != nil || port < 1 || port > 65535 {
		return "", 0, "", fmt.Errorf("invalid probe port %q", portText)
	}
	return host, port, net.JoinHostPort(host, strconv.Itoa(port)), nil
}

func normalizeProbeTargets(targets []string) []string {
	normalized := make([]string, 0, len(targets))
	seen := make(map[string]struct{})
	for _, target := range targets {
		target = strings.TrimSpace(target)
		if target == "" {
			continue
		}
		key := strings.ToLower(target)
		if _, exists := seen[key]; exists {
			continue
		}
		seen[key] = struct{}{}
		normalized = append(normalized, target)
	}
	return normalized
}

func isTLSCandidate(connection TCPConnection) bool {
	_, localTLS := defaultTLSPorts[connection.LocalPort]
	_, remoteTLS := defaultTLSPorts[connection.RemotePort]
	return localTLS || remoteTLS
}

func connectionKey(connection TCPConnection) string {
	return fmt.Sprintf("%s:%d>%s:%d:%d", connection.LocalIP, connection.LocalPort, connection.RemoteIP, connection.RemotePort, connection.PID)
}

func tlsVersionName(version uint16) string {
	switch version {
	case tls.VersionTLS10:
		return "TLS 1.0"
	case tls.VersionTLS11:
		return "TLS 1.1"
	case tls.VersionTLS12:
		return "TLS 1.2"
	case tls.VersionTLS13:
		return "TLS 1.3"
	default:
		return fmt.Sprintf("0x%04X", version)
	}
}
