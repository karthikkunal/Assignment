package discovery

import (
	"context"
	"crypto/ed25519"
	"crypto/rand"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"math/big"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestFilesystemScannerExtractsAndDeduplicatesCertificates(t *testing.T) {
	t.Parallel()

	now := time.Date(2026, 10, 9, 12, 0, 0, 0, time.UTC)
	der := createTestCertificate(t, now.Add(-time.Hour), now.Add(90*24*time.Hour))
	root := t.TempDir()
	writeFile(t, filepath.Join(root, "service.pem"), pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der}))
	writeFile(t, filepath.Join(root, "service-copy.crt"), pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der}))
	writeFile(t, filepath.Join(root, "service.der"), der)

	scanner := NewFilesystemScanner()
	scanner.Now = func() time.Time { return now }
	observations, scanErrors := scanner.Scan(context.Background(), []string{root})

	if len(scanErrors) != 0 {
		t.Fatalf("expected no scan errors, got %v", scanErrors)
	}
	if len(observations) != 3 {
		t.Fatalf("expected 3 location observations, got %d", len(observations))
	}

	fingerprint := observations[0].FingerprintSHA256
	duplicates := 0
	for _, observation := range observations {
		if observation.ParsingStatus != "parsed" {
			t.Errorf("expected parsed observation, got %q", observation.ParsingStatus)
		}
		if observation.FingerprintSHA256 != fingerprint {
			t.Errorf("expected stable fingerprint %q, got %q", fingerprint, observation.FingerprintSHA256)
		}
		if observation.ValidityStatus != "valid" {
			t.Errorf("expected valid posture, got %q", observation.ValidityStatus)
		}
		if observation.PublicKeyAlgorithm != "Ed25519" || observation.PublicKeySize != 256 {
			t.Errorf("unexpected key posture: %s/%d", observation.PublicKeyAlgorithm, observation.PublicKeySize)
		}
		if observation.Duplicate {
			duplicates++
		}
	}
	if duplicates != 2 {
		t.Fatalf("expected 2 duplicate location observations, got %d", duplicates)
	}
}

func TestFilesystemScannerRecordsProtectedContainerWithoutOpeningIt(t *testing.T) {
	t.Parallel()

	root := t.TempDir()
	writeFile(t, filepath.Join(root, "protected.p12"), []byte("not-key-material"))

	observations, scanErrors := NewFilesystemScanner().Scan(context.Background(), []string{root})
	if len(scanErrors) != 0 {
		t.Fatalf("expected no scan errors, got %v", scanErrors)
	}
	if len(observations) != 1 || observations[0].ParsingStatus != "parse_failed" {
		t.Fatalf("expected one recorded parse failure, got %#v", observations)
	}
}

func createTestCertificate(t *testing.T, notBefore, notAfter time.Time) []byte {
	t.Helper()
	publicKey, privateKey, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatalf("generate key: %v", err)
	}
	template := &x509.Certificate{
		SerialNumber: big.NewInt(42),
		Subject:      pkix.Name{CommonName: "inventory.test"},
		Issuer:       pkix.Name{CommonName: "QuantumGenie Test CA"},
		DNSNames:     []string{"inventory.test"},
		NotBefore:    notBefore,
		NotAfter:     notAfter,
		KeyUsage:     x509.KeyUsageDigitalSignature,
	}
	der, err := x509.CreateCertificate(rand.Reader, template, template, publicKey, privateKey)
	if err != nil {
		t.Fatalf("create certificate: %v", err)
	}
	return der
}

func writeFile(t *testing.T, path string, data []byte) {
	t.Helper()
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatalf("write %s: %v", path, err)
	}
}
