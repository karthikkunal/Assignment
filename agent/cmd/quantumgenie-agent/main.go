package main

import (
	"context"
	"errors"
	"flag"
	"io"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/quantumgenie/discovery-agent/internal/agent"
)

const version = "0.1.0"

func main() {
	listenAddress := flag.String("listen", "127.0.0.1:8766", "loopback address for agent commands")
	backendURL := flag.String("backend", "http://127.0.0.1:8765", "local backend callback URL")
	token := flag.String("token", os.Getenv("QG_AGENT_TOKEN"), "shared local agent token")
	logFile := flag.String("log-file", defaultLogPath(), "agent log file; empty disables file logging")
	showVersion := flag.Bool("version", false, "print agent version")
	flag.Parse()
	if *showVersion {
		println(version)
		return
	}
	if err := validateLoopbackAddress(*listenAddress); err != nil {
		println(err.Error())
		os.Exit(2)
	}

	logWriter, closeLog := createLogWriter(*logFile)
	defer closeLog()
	logger := slog.New(slog.NewJSONHandler(logWriter, &slog.HandlerOptions{Level: slog.LevelInfo}))

	shutdownSignal, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	runner, err := agent.NewRunner(shutdownSignal, *backendURL, *token, version, logger)
	if err != nil {
		logger.Error("invalid agent configuration", "error", err)
		os.Exit(2)
	}
	handler := agent.NewServer(runner, *token, version).Handler()

	server := &http.Server{
		Addr:              *listenAddress,
		Handler:           handler,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       30 * time.Second,
	}

	go func() {
		<-shutdownSignal.Done()
		shutdownContext, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := server.Shutdown(shutdownContext); err != nil {
			logger.Error("agent shutdown failed", "error", err)
		}
	}()

	logger.Info("agent listening", "address", *listenAddress, "version", version)
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		logger.Error("agent stopped unexpectedly", "error", err)
		os.Exit(1)
	}
}

func validateLoopbackAddress(address string) error {
	host, _, err := net.SplitHostPort(address)
	if err != nil {
		return errors.New("listen address must be host:port")
	}
	if strings.EqualFold(host, "localhost") {
		return nil
	}
	ip := net.ParseIP(host)
	if ip == nil || !ip.IsLoopback() {
		return errors.New("agent commands must listen on a loopback address")
	}
	return nil
}

func defaultLogPath() string {
	base := os.Getenv("LOCALAPPDATA")
	if base == "" {
		base = os.TempDir()
	}
	return filepath.Join(base, "QuantumGenie", "agent.log")
}

func createLogWriter(path string) (io.Writer, func()) {
	if path == "" {
		return os.Stdout, func() {}
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return os.Stdout, func() {}
	}
	file, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o600)
	if err != nil {
		return os.Stdout, func() {}
	}
	return io.MultiWriter(os.Stdout, file), func() { _ = file.Close() }
}
