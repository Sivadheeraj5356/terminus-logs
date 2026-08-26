package wire

import (
	"bytes"
	"fmt"
	"net/textproto"
	"sigproxy/internal/semantics"
)

// EncodeBackend writes a deterministic HTTP/1.1 request from a semantic request.
func EncodeBackend(sem *semantics.Request) []byte {
	var buf bytes.Buffer
	target := sem.CanonicalPath
	if sem.CanonicalQuery != "" {
		target = target + "?" + sem.CanonicalQuery
	}
	if target == "" {
		target = sem.CanonicalTarget
	}
	fmt.Fprintf(&buf, "%s %s HTTP/1.1\r\n", sem.Method, target)
	for _, h := range sem.CanonicalHeaders {
		fmt.Fprintf(&buf, "%s: %s\r\n", textproto.CanonicalMIMEHeaderKey(h.Name), h.Value)
	}
	fmt.Fprintf(&buf, "Content-Length: %d\r\n", len(sem.EntityBody))
	fmt.Fprintf(&buf, "\r\n")
	buf.Write(sem.EntityBody)
	return buf.Bytes()
}
