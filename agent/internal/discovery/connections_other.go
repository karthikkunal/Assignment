//go:build !windows

package discovery

import "fmt"

func listTCPConnections() ([]TCPConnection, error) {
	return nil, fmt.Errorf("TCP process ownership discovery is supported on Windows only")
}
