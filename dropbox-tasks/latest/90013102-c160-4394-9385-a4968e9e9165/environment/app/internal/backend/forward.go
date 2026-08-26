package backend

import (
	"io"
	"net"
	"strings"

	"sigproxy/internal/digest"
	"sigproxy/internal/semantics"
	"sigproxy/internal/wire"
)

type ForwardResult struct {
	BackendBytes  []byte
	BackendDigest string
	BackendLength int
	StatusCode    int
	ResponseBody  []byte
}

func ForwardSemantic(backendUnix string, sem *semantics.Request) (*ForwardResult, error) {
	payload := wire.EncodeBackend(sem)
	conn, err := net.Dial("unix", backendUnix)
	if err != nil {
		return nil, err
	}
	defer conn.Close()
	if _, err := conn.Write(payload); err != nil {
		return nil, err
	}
	resp, err := io.ReadAll(conn)
	if err != nil {
		return nil, err
	}
	code := parseStatusCode(string(resp))
	return &ForwardResult{
		BackendBytes:  payload,
		BackendDigest: digest.SHA256(payload),
		BackendLength: len(payload),
		StatusCode:    code,
		ResponseBody:  resp,
	}, nil
}

func parseStatusCode(raw string) int {
	line := raw
	if idx := strings.Index(raw, "\r\n"); idx >= 0 {
		line = raw[:idx]
	} else if idx := strings.Index(raw, "\n"); idx >= 0 {
		line = raw[:idx]
	}
	fields := strings.Fields(line)
	if len(fields) < 2 {
		return 0
	}
	var code int
	for _, c := range fields[1] {
		if c >= '0' && c <= '9' {
			code = code*10 + int(c-'0')
		} else {
			break
		}
	}
	return code
}
