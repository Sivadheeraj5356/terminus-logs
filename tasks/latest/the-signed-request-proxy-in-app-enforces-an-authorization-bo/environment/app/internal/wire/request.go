package wire

import "sigproxy/internal/digest"

// Request holds the raw HTTP/1.1 request as received on the wire.
type Request struct {
	RawBytes       []byte
	Method         string
	Target         string
	Version        string
	HeaderOrder    []string
	Headers        map[string][]string
	EntityBody     []byte
	TransferCoding string
}

func (r *Request) WireDigest() string {
	return digest.SHA256(r.RawBytes)
}

func (r *Request) EntityDigest() string {
	return digest.SHA256(r.EntityBody)
}

func HeaderFirst(headers map[string][]string, name string) string {
	vals, ok := headers[name]
	if !ok || len(vals) == 0 {
		return ""
	}
	return vals[0]
}
