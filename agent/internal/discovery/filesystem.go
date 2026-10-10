package discovery

import (
	"context"
	"crypto/dsa"
	"crypto/ecdsa"
	"crypto/ed25519"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/hex"
	"encoding/pem"
	"errors"
	"fmt"
	"io/fs"
	"math"
	"os"
	"path/filepath"
	"runtime"
	"slices"
	"strings"
	"time"

	"github.com/quantumgenie/discovery-agent/internal/model"
)

const defaultMaxCertificateFileSize = 16 << 20

var supportedCertificateExtensions = map[string]string{
	".pem": "PEM",
	".der": "DER",
	".crt": "CRT",
	".cer": "CER",
	".pfx": "PFX",
	".p12": "P12",
	".p7b": "PKCS7",
	".p7c": "PKCS7",
	".jks": "JKS",
}

type FilesystemScanner struct {
	MaxFileSize        int64
	ExpiringWithinDays int
	Now                func() time.Time
}

func NewFilesystemScanner() *FilesystemScanner {
	return &FilesystemScanner{
		MaxFileSize:        defaultMaxCertificateFileSize,
		ExpiringWithinDays: 30,
		Now:                time.Now,
	}
}

func DefaultCertificateRoots() []string {
	if runtime.GOOS != "windows" {
		return []string{"/etc/ssl", "/usr/local/share/ca-certificates"}
	}

	roots := make([]string, 0, 4)
	if programData := os.Getenv("ProgramData"); programData != "" {
		roots = append(roots, filepath.Join(programData, "Microsoft", "SystemCertificates"))
	}
	if appData := os.Getenv("APPDATA"); appData != "" {
		roots = append(roots, filepath.Join(appData, "Microsoft", "SystemCertificates"))
	}
	if userProfile := os.Getenv("USERPROFILE"); userProfile != "" {
		roots = append(roots, filepath.Join(userProfile, ".certs"))
	}
	return roots
}

func (scanner *FilesystemScanner) Scan(ctx context.Context, roots []string) ([]model.CertificateObservation, []model.ScanError) {
	if len(roots) == 0 {
		roots = DefaultCertificateRoots()
	}

	observations := make([]model.CertificateObservation, 0)
	scanErrors := make([]model.ScanError, 0)
	firstPathByFingerprint := make(map[string]string)
	visitedPaths := make(map[string]struct{})

	for _, root := range normalizeRoots(roots) {
		if err := ctx.Err(); err != nil {
			scanErrors = append(scanErrors, model.ScanError{Path: root, Message: err.Error()})
			break
		}

		walkErr := filepath.WalkDir(root, func(path string, entry fs.DirEntry, walkErr error) error {
			if err := ctx.Err(); err != nil {
				return err
			}
			if walkErr != nil {
				scanErrors = append(scanErrors, model.ScanError{Path: path, Message: walkErr.Error()})
				if entry != nil && entry.IsDir() {
					return filepath.SkipDir
				}
				return nil
			}
			if entry.IsDir() {
				if path != root && shouldSkipDirectory(entry.Name()) {
					return filepath.SkipDir
				}
				return nil
			}
			if entry.Type()&os.ModeSymlink != 0 {
				return nil
			}

			format, supported := supportedCertificateExtensions[strings.ToLower(filepath.Ext(path))]
			if !supported {
				return nil
			}
			canonicalPath := strings.ToLower(filepath.Clean(path))
			if _, visited := visitedPaths[canonicalPath]; visited {
				return nil
			}
			visitedPaths[canonicalPath] = struct{}{}

			fileObservations := scanner.inspectFile(path, root, format)
			for index := range fileObservations {
				observation := &fileObservations[index]
				if observation.FingerprintSHA256 != "" {
					if firstPath, duplicate := firstPathByFingerprint[observation.FingerprintSHA256]; duplicate {
						observation.Duplicate = true
						observation.DuplicateOf = firstPath
					} else {
						firstPathByFingerprint[observation.FingerprintSHA256] = observation.Path
					}
				}
			}
			observations = append(observations, fileObservations...)
			return nil
		})
		if walkErr != nil && !errors.Is(walkErr, context.Canceled) {
			scanErrors = append(scanErrors, model.ScanError{Path: root, Message: walkErr.Error()})
		}
	}

	return observations, scanErrors
}

func (scanner *FilesystemScanner) inspectFile(path, root, format string) []model.CertificateObservation {
	discoveredAt := scanner.Now().UTC()
	base := model.CertificateObservation{
		Path:               path,
		Filename:           filepath.Base(path),
		Format:             format,
		DiscoveredAt:       discoveredAt,
		ScanRoot:           root,
		SANEntries:         []string{},
		OwnerProcess:       "unavailable",
		ValidityStatus:     "unknown",
		EvidenceConfidence: "low",
	}

	info, err := os.Stat(path)
	if err != nil {
		base.ParsingStatus = "access_error"
		base.AccessError = err.Error()
		return []model.CertificateObservation{base}
	}
	maxFileSize := scanner.MaxFileSize
	if maxFileSize <= 0 {
		maxFileSize = defaultMaxCertificateFileSize
	}
	if info.Size() > maxFileSize {
		base.ParsingStatus = "skipped_too_large"
		base.AccessError = fmt.Sprintf("file is %d bytes; safety limit is %d bytes", info.Size(), maxFileSize)
		return []model.CertificateObservation{base}
	}

	data, err := os.ReadFile(path)
	if err != nil {
		base.ParsingStatus = "access_error"
		base.AccessError = err.Error()
		return []model.CertificateObservation{base}
	}

	certificates, err := parseCertificates(data, format)
	if err != nil {
		base.ParsingStatus = "parse_failed"
		base.AccessError = err.Error()
		return []model.CertificateObservation{base}
	}

	observations := make([]model.CertificateObservation, 0, len(certificates))
	for index, certificate := range certificates {
		observation := base
		observation.ChainPosition = index
		populateCertificateMetadata(&observation, certificate, discoveredAt, scanner.ExpiringWithinDays)
		observations = append(observations, observation)
	}
	return observations
}

func parseCertificates(data []byte, format string) ([]*x509.Certificate, error) {
	switch format {
	case "PFX", "P12":
		return nil, errors.New("PKCS#12 container detected; password-protected key material is intentionally not opened")
	case "PKCS7":
		return nil, errors.New("PKCS#7 container detected; this build records the file but does not decode the container")
	case "JKS":
		return nil, errors.New("Java keystore detected; this build records the file but does not request keystore credentials")
	}

	if format == "PEM" || strings.Contains(string(data[:min(len(data), 64)]), "-----BEGIN") {
		certificates := make([]*x509.Certificate, 0)
		remaining := data
		for len(remaining) > 0 {
			block, rest := pem.Decode(remaining)
			if block == nil {
				break
			}
			remaining = rest
			if block.Type != "CERTIFICATE" {
				continue
			}
			certificate, err := x509.ParseCertificate(block.Bytes)
			if err != nil {
				return nil, fmt.Errorf("parse PEM certificate: %w", err)
			}
			certificates = append(certificates, certificate)
		}
		if len(certificates) == 0 {
			return nil, errors.New("no certificate blocks found")
		}
		return certificates, nil
	}

	certificates, err := x509.ParseCertificates(data)
	if err != nil {
		return nil, fmt.Errorf("parse DER certificate: %w", err)
	}
	return certificates, nil
}

func populateCertificateMetadata(observation *model.CertificateObservation, certificate *x509.Certificate, observedAt time.Time, expiringWithinDays int) {
	fingerprint := sha256.Sum256(certificate.Raw)
	daysToExpiry := int(math.Floor(certificate.NotAfter.Sub(observedAt).Hours() / 24))
	validFrom := certificate.NotBefore.UTC()
	validTo := certificate.NotAfter.UTC()

	observation.FingerprintSHA256 = strings.ToUpper(hex.EncodeToString(fingerprint[:]))
	observation.SerialNumber = strings.ToUpper(certificate.SerialNumber.Text(16))
	observation.Subject = certificate.Subject.String()
	observation.Issuer = certificate.Issuer.String()
	observation.SANEntries = certificateSANs(certificate)
	observation.PublicKeyAlgorithm = certificate.PublicKeyAlgorithm.String()
	observation.PublicKeySize = publicKeySize(certificate.PublicKey)
	observation.SignatureAlgorithm = certificate.SignatureAlgorithm.String()
	observation.ValidFrom = &validFrom
	observation.ValidTo = &validTo
	observation.DaysToExpiry = &daysToExpiry
	observation.ValidityStatus = certificateValidityStatus(certificate, observedAt, expiringWithinDays)
	observation.ParsingStatus = "parsed"
	observation.EvidenceConfidence = "high"
}

func certificateValidityStatus(certificate *x509.Certificate, observedAt time.Time, expiringWithinDays int) string {
	if observedAt.Before(certificate.NotBefore) {
		return "not_yet_valid"
	}
	if observedAt.After(certificate.NotAfter) {
		return "expired"
	}
	if certificate.NotAfter.Sub(observedAt) <= time.Duration(expiringWithinDays)*24*time.Hour {
		return "expiring"
	}
	return "valid"
}

func certificateSANs(certificate *x509.Certificate) []string {
	entries := make([]string, 0, len(certificate.DNSNames)+len(certificate.IPAddresses)+len(certificate.EmailAddresses)+len(certificate.URIs))
	entries = append(entries, certificate.DNSNames...)
	for _, address := range certificate.IPAddresses {
		entries = append(entries, address.String())
	}
	entries = append(entries, certificate.EmailAddresses...)
	for _, uri := range certificate.URIs {
		entries = append(entries, uri.String())
	}
	slices.Sort(entries)
	return slices.Compact(entries)
}

func publicKeySize(publicKey any) int {
	switch key := publicKey.(type) {
	case *rsa.PublicKey:
		return key.N.BitLen()
	case *ecdsa.PublicKey:
		return key.Curve.Params().BitSize
	case ed25519.PublicKey:
		return len(key) * 8
	case *dsa.PublicKey:
		return key.P.BitLen()
	default:
		return 0
	}
}

func normalizeRoots(roots []string) []string {
	normalized := make([]string, 0, len(roots))
	seen := make(map[string]struct{})
	for _, root := range roots {
		root = strings.TrimSpace(os.ExpandEnv(root))
		if root == "" {
			continue
		}
		absoluteRoot, err := filepath.Abs(root)
		if err != nil {
			absoluteRoot = filepath.Clean(root)
		}
		key := strings.ToLower(absoluteRoot)
		if _, exists := seen[key]; exists {
			continue
		}
		seen[key] = struct{}{}
		normalized = append(normalized, absoluteRoot)
	}
	return normalized
}

func shouldSkipDirectory(name string) bool {
	return strings.EqualFold(name, "$Recycle.Bin") ||
		strings.EqualFold(name, "System Volume Information") ||
		strings.EqualFold(name, "node_modules") ||
		strings.EqualFold(name, ".git")
}
