package agent

import (
	"crypto/subtle"
	"encoding/json"
	"errors"
	"net/http"
	"regexp"
	"runtime"
	"strings"

	"github.com/quantumgenie/discovery-agent/internal/model"
)

var validRunID = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$`)

type Server struct {
	runner  *Runner
	token   string
	version string
}

func NewServer(runner *Runner, token, version string) *Server {
	return &Server{runner: runner, token: token, version: version}
}

func (server *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", server.handleHealth)
	mux.Handle("POST /v1/scans/filesystem", server.authorize(http.HandlerFunc(server.handleFilesystemScan)))
	mux.Handle("POST /v1/scans/tls", server.authorize(http.HandlerFunc(server.handleTLSScan)))
	return server.secureHeaders(mux)
}

func (server *Server) handleHealth(response http.ResponseWriter, _ *http.Request) {
	writeJSON(response, http.StatusOK, map[string]any{
		"status":      "healthy",
		"version":     server.version,
		"os":          runtime.GOOS,
		"active_runs": server.runner.ActiveRunCount(),
	})
}

func (server *Server) handleFilesystemScan(response http.ResponseWriter, request *http.Request) {
	var command model.FilesystemScanRequest
	if err := decodeJSON(response, request, &command); err != nil {
		writeJSON(response, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	if !validRunID.MatchString(command.RunID) {
		writeJSON(response, http.StatusUnprocessableEntity, map[string]string{"error": "run_id must be 1-128 letters, numbers, underscores, or hyphens"})
		return
	}
	if len(command.Roots) > 32 {
		writeJSON(response, http.StatusUnprocessableEntity, map[string]string{"error": "at most 32 scan roots are allowed"})
		return
	}
	if err := server.runner.StartFilesystem(command); err != nil {
		server.writeStartError(response, err)
		return
	}
	writeJSON(response, http.StatusAccepted, map[string]string{"run_id": command.RunID, "status": "accepted"})
}

func (server *Server) handleTLSScan(response http.ResponseWriter, request *http.Request) {
	var command model.TLSScanRequest
	if err := decodeJSON(response, request, &command); err != nil {
		writeJSON(response, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	if !validRunID.MatchString(command.RunID) {
		writeJSON(response, http.StatusUnprocessableEntity, map[string]string{"error": "run_id must be 1-128 letters, numbers, underscores, or hyphens"})
		return
	}
	if command.DurationSeconds == 0 {
		command.DurationSeconds = 15
	}
	if command.DurationSeconds < 1 || command.DurationSeconds > 300 {
		writeJSON(response, http.StatusUnprocessableEntity, map[string]string{"error": "duration_seconds must be between 1 and 300"})
		return
	}
	if len(command.ProbeTargets) > 32 {
		writeJSON(response, http.StatusUnprocessableEntity, map[string]string{"error": "at most 32 probe targets are allowed"})
		return
	}
	if err := server.runner.StartTLS(command); err != nil {
		server.writeStartError(response, err)
		return
	}
	writeJSON(response, http.StatusAccepted, map[string]string{"run_id": command.RunID, "status": "accepted"})
}

func (server *Server) writeStartError(response http.ResponseWriter, err error) {
	if errors.Is(err, ErrRunAlreadyActive) {
		writeJSON(response, http.StatusConflict, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(response, http.StatusInternalServerError, map[string]string{"error": "unable to start scan"})
}

func (server *Server) authorize(next http.Handler) http.Handler {
	if server.token == "" {
		return next
	}
	return http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		providedToken := request.Header.Get("X-Agent-Token")
		if subtle.ConstantTimeCompare([]byte(providedToken), []byte(server.token)) != 1 {
			writeJSON(response, http.StatusUnauthorized, map[string]string{"error": "invalid agent token"})
			return
		}
		next.ServeHTTP(response, request)
	})
}

func (server *Server) secureHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		response.Header().Set("Cache-Control", "no-store")
		response.Header().Set("X-Content-Type-Options", "nosniff")
		next.ServeHTTP(response, request)
	})
}

func decodeJSON(response http.ResponseWriter, request *http.Request, destination any) error {
	request.Body = http.MaxBytesReader(response, request.Body, 1<<20)
	decoder := json.NewDecoder(request.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(destination); err != nil {
		return err
	}
	if decoder.More() {
		return errors.New("request must contain one JSON object")
	}
	return nil
}

func writeJSON(response http.ResponseWriter, status int, value any) {
	response.Header().Set("Content-Type", "application/json")
	response.WriteHeader(status)
	if err := json.NewEncoder(response).Encode(value); err != nil && !strings.Contains(err.Error(), "closed") {
		return
	}
}
