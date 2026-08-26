// server_harness.go — helpers for starting and stopping the WEBrick server
// under test.
package proptest

import (
	"fmt"
	"net"
	"net/http"
	"os/exec"
	"time"
)

// ServerHandle holds the running server subprocess and its address.
type ServerHandle struct {
	cmd  *exec.Cmd
	addr string
}

// StartServer launches the WEBrick service from /app/server.rb on a free port
// and blocks until the health endpoint responds or the timeout expires.
// Set PORT, BIND_ADDR=127.0.0.1, and RATE_LIMIT_RPM=10000 on the subprocess
// environment; pass the full parent env through. Ensure RUBYOPT contains
// -rbundler/setup without wiping other parent RUBYOPT flags. Returns a
// ServerHandle for StopServer.
func StartServer() (*ServerHandle, error) {
	port, err := freePort()
	if err != nil {
		return nil, fmt.Errorf("no free port: %w", err)
	}

	addr := fmt.Sprintf("127.0.0.1:%d", port)

	_ = addr
	return nil, fmt.Errorf("StartServer not implemented")
}

// StopServer terminates the server subprocess started by StartServer.
func StopServer(h *ServerHandle) {
	if h == nil || h.cmd == nil {
		return
	}
}

// BaseURL returns the HTTP base URL for the running server.
func (h *ServerHandle) BaseURL() string {
	return "http://" + h.addr
}

// waitHealthy polls the /health endpoint until it returns 200 or the deadline passes.
func waitHealthy(addr string, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	client   := &http.Client{Timeout: 500 * time.Millisecond}
	url      := "http://" + addr + "/health"
	for time.Now().Before(deadline) {
		resp, err := client.Get(url)
		if err == nil && resp.StatusCode == 200 {
			resp.Body.Close()
			return nil
		}
		time.Sleep(100 * time.Millisecond)
	}
	return fmt.Errorf("server at %s did not become healthy within %s", addr, timeout)
}

// freePort asks the OS for an available TCP port.
func freePort() (int, error) {
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return 0, err
	}
	defer l.Close()
	return l.Addr().(*net.TCPAddr).Port, nil
}
