package ready

import (
	"net"
)

// ProbeListen opens a TCP socket for superficial readiness checks.
func ProbeListen(addr string) (net.Listener, error) {
	return net.Listen("tcp", addr)
}
