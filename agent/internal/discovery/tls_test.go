package discovery

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestTLSScannerProbeTargetCapturesHandshakeMetadata(t *testing.T) {
	t.Parallel()

	server := httptest.NewTLSServer(http.HandlerFunc(func(response http.ResponseWriter, _ *http.Request) {
		response.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	scanner := NewTLSScanner()
	scanner.DialTimeout = 2 * time.Second
	observation := scanner.ProbeTarget(context.Background(), server.URL)

	if observation.HandshakeOutcome != "succeeded" {
		t.Fatalf("expected successful handshake, got %q: %s", observation.HandshakeOutcome, observation.Error)
	}
	if observation.TLSVersion == "" || observation.CipherSuite == "" {
		t.Fatalf("expected TLS version and cipher suite, got %#v", observation)
	}
	if observation.PeerCertificateFingerprint == "" || observation.PeerCertificateSubject == "" {
		t.Fatalf("expected peer certificate evidence, got %#v", observation)
	}
	if observation.CaptureMethod != "active_metadata_probe" || observation.EventCount != 1 {
		t.Fatalf("unexpected evidence metadata: %#v", observation)
	}
}

func TestParseProbeTargetDefaultsToHTTPS(t *testing.T) {
	t.Parallel()

	host, port, target, err := parseProbeTarget("example.com")
	if err != nil {
		t.Fatalf("parse target: %v", err)
	}
	if host != "example.com" || port != 443 || target != "example.com:443" {
		t.Fatalf("unexpected target: host=%q port=%d target=%q", host, port, target)
	}
}
