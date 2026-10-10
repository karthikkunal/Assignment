package agent

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"

	"github.com/quantumgenie/discovery-agent/internal/discovery"
	"github.com/quantumgenie/discovery-agent/internal/model"
)

var ErrRunAlreadyActive = errors.New("run is already active")

type Runner struct {
	context           context.Context
	backendURL        string
	token             string
	version           string
	client            *http.Client
	logger            *slog.Logger
	filesystemScanner *discovery.FilesystemScanner
	tlsScanner        *discovery.TLSScanner
	mutex             sync.Mutex
	activeRuns        map[string]struct{}
}

func NewRunner(ctx context.Context, backendURL, token, version string, logger *slog.Logger) (*Runner, error) {
	parsedBackendURL, err := url.Parse(strings.TrimRight(backendURL, "/"))
	if err != nil || parsedBackendURL.Scheme == "" || parsedBackendURL.Host == "" {
		return nil, fmt.Errorf("invalid backend URL %q", backendURL)
	}
	if parsedBackendURL.Scheme != "http" && parsedBackendURL.Scheme != "https" {
		return nil, fmt.Errorf("backend URL must use http or https")
	}

	return &Runner{
		context:           ctx,
		backendURL:        parsedBackendURL.String(),
		token:             token,
		version:           version,
		client:            &http.Client{Timeout: 15 * time.Second},
		logger:            logger,
		filesystemScanner: discovery.NewFilesystemScanner(),
		tlsScanner:        discovery.NewTLSScanner(),
		activeRuns:        make(map[string]struct{}),
	}, nil
}

func (runner *Runner) StartFilesystem(request model.FilesystemScanRequest) error {
	if err := runner.reserve(request.RunID); err != nil {
		return err
	}
	go runner.runFilesystem(request)
	return nil
}

func (runner *Runner) StartTLS(request model.TLSScanRequest) error {
	if err := runner.reserve(request.RunID); err != nil {
		return err
	}
	go runner.runTLS(request)
	return nil
}

func (runner *Runner) ActiveRunCount() int {
	runner.mutex.Lock()
	defer runner.mutex.Unlock()
	return len(runner.activeRuns)
}

func (runner *Runner) runFilesystem(request model.FilesystemScanRequest) {
	defer runner.release(request.RunID)
	startedAt := time.Now().UTC()
	runner.logger.Info("filesystem scan started", "run_id", request.RunID, "roots", request.Roots)
	runner.postStatus(request.RunID, "running", "filesystem discovery started")

	observations, scanErrors := runner.filesystemScanner.Scan(runner.context, request.Roots)
	completedAt := time.Now().UTC()
	status := completedStatus(len(observations), scanErrors)
	result := model.FilesystemScanResult{
		RunID:        request.RunID,
		Status:       status,
		StartedAt:    startedAt,
		CompletedAt:  completedAt,
		AgentVersion: runner.version,
		Observations: observations,
		Errors:       scanErrors,
	}
	if err := runner.postWithRetry("/api/v1/agent/results/filesystem", result); err != nil {
		runner.logger.Error("filesystem result delivery failed", "run_id", request.RunID, "error", err)
	}
	runner.logger.Info("filesystem scan finished", "run_id", request.RunID, "status", status, "records", len(observations), "errors", len(scanErrors), "duration_ms", completedAt.Sub(startedAt).Milliseconds())
}

func (runner *Runner) runTLS(request model.TLSScanRequest) {
	defer runner.release(request.RunID)
	startedAt := time.Now().UTC()
	duration := time.Duration(request.DurationSeconds) * time.Second
	runner.logger.Info("TLS metadata scan started", "run_id", request.RunID, "duration_seconds", request.DurationSeconds, "probe_targets", request.ProbeTargets)
	runner.postStatus(request.RunID, "running", "TLS metadata observation started")

	observations, scanErrors := runner.tlsScanner.Scan(runner.context, duration, request.ProbeTargets)
	completedAt := time.Now().UTC()
	status := completedStatus(len(observations), scanErrors)
	result := model.TLSScanResult{
		RunID:        request.RunID,
		Status:       status,
		StartedAt:    startedAt,
		CompletedAt:  completedAt,
		AgentVersion: runner.version,
		Observations: observations,
		Errors:       scanErrors,
	}
	if err := runner.postWithRetry("/api/v1/agent/results/tls", result); err != nil {
		runner.logger.Error("TLS result delivery failed", "run_id", request.RunID, "error", err)
	}
	runner.logger.Info("TLS metadata scan finished", "run_id", request.RunID, "status", status, "records", len(observations), "errors", len(scanErrors), "duration_ms", completedAt.Sub(startedAt).Milliseconds())
}

func (runner *Runner) reserve(runID string) error {
	runner.mutex.Lock()
	defer runner.mutex.Unlock()
	if _, exists := runner.activeRuns[runID]; exists {
		return ErrRunAlreadyActive
	}
	runner.activeRuns[runID] = struct{}{}
	return nil
}

func (runner *Runner) release(runID string) {
	runner.mutex.Lock()
	delete(runner.activeRuns, runID)
	runner.mutex.Unlock()
}

func (runner *Runner) postStatus(runID, status, message string) {
	update := model.StatusUpdate{Status: status, Timestamp: time.Now().UTC(), Message: message}
	endpoint := "/api/v1/agent/runs/" + url.PathEscape(runID) + "/status"
	if err := runner.postJSON(runner.context, endpoint, update); err != nil {
		runner.logger.Warn("run status callback failed", "run_id", runID, "status", status, "error", err)
	}
}

func (runner *Runner) postWithRetry(endpoint string, value any) error {
	delays := []time.Duration{0, 500 * time.Millisecond, 1500 * time.Millisecond, 3 * time.Second}
	var lastError error
	for _, delay := range delays {
		if delay > 0 {
			select {
			case <-runner.context.Done():
				return runner.context.Err()
			case <-time.After(delay):
			}
		}
		if err := runner.postJSON(runner.context, endpoint, value); err != nil {
			lastError = err
			continue
		}
		return nil
	}
	return lastError
}

func (runner *Runner) postJSON(ctx context.Context, endpoint string, value any) error {
	body, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("encode callback: %w", err)
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodPost, runner.backendURL+endpoint, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("create callback: %w", err)
	}
	request.Header.Set("Content-Type", "application/json")
	if runner.token != "" {
		request.Header.Set("X-Agent-Token", runner.token)
	}
	response, err := runner.client.Do(request)
	if err != nil {
		return fmt.Errorf("send callback: %w", err)
	}
	defer response.Body.Close()
	if response.StatusCode < http.StatusOK || response.StatusCode >= http.StatusMultipleChoices {
		return fmt.Errorf("callback returned %s", response.Status)
	}
	return nil
}

func completedStatus(recordCount int, scanErrors []model.ScanError) string {
	if len(scanErrors) == 0 {
		return "completed"
	}
	if recordCount == 0 {
		return "failed"
	}
	return "partial"
}
