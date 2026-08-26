package wire

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"net/textproto"
	"strings"
)

func Parse(raw []byte) (*Request, error) {
	reader := bufio.NewReader(bytes.NewReader(raw))
	reqLine, err := reader.ReadString('\n')
	if err != nil {
		return nil, fmt.Errorf("parse request line: %w", err)
	}
	reqLine = strings.TrimSpace(reqLine)
	parts := strings.SplitN(reqLine, " ", 3)
	if len(parts) != 3 {
		return nil, fmt.Errorf("invalid request line: %q", reqLine)
	}

	tp := textproto.NewReader(reader)
	mimeHeader, err := tp.ReadMIMEHeader()
	if err != nil {
		return nil, fmt.Errorf("parse headers: %w", err)
	}

	headers := make(map[string][]string)
	for k, vals := range mimeHeader {
		canonical := textproto.CanonicalMIMEHeaderKey(k)
		headers[canonical] = append([]string(nil), vals...)
	}
	order := headerOrderFromRaw(raw)

	transferCoding := ""
	if vals := headers["Transfer-Encoding"]; len(vals) > 0 {
		transferCoding = strings.ToLower(strings.TrimSpace(vals[0]))
	}

	var entityBody []byte
	contentLength := -1
	if vals := headers["Content-Length"]; len(vals) > 0 {
		if len(vals) > 1 {
			return nil, fmt.Errorf("duplicate Content-Length")
		}
		var n int
		if _, err := fmt.Sscanf(vals[0], "%d", &n); err != nil {
			return nil, fmt.Errorf("invalid Content-Length: %w", err)
		}
		contentLength = n
	}

	if transferCoding == "chunked" {
		if contentLength >= 0 {
			return nil, fmt.Errorf("conflicting Transfer-Encoding and Content-Length")
		}
		rest, err := io.ReadAll(reader)
		if err != nil {
			return nil, err
		}
		entityBody, err = DecodeChunked(rest)
		if err != nil {
			return nil, err
		}
	} else if contentLength >= 0 {
		entityBody = make([]byte, contentLength)
		if _, err := io.ReadFull(reader, entityBody); err != nil {
			return nil, fmt.Errorf("read body: %w", err)
		}
	} else {
		rest, _ := io.ReadAll(reader)
		entityBody = rest
	}

	return &Request{
		RawBytes:       append([]byte(nil), raw...),
		Method:         parts[0],
		Target:         parts[1],
		Version:        parts[2],
		HeaderOrder:    order,
		Headers:        headers,
		EntityBody:     entityBody,
		TransferCoding: transferCoding,
	}, nil
}

func headerOrderFromRaw(raw []byte) []string {
	lines := strings.Split(string(raw), "\n")
	if len(lines) == 0 {
		return nil
	}
	order := make([]string, 0)
	seen := make(map[string]bool)
	for i := 1; i < len(lines); i++ {
		line := strings.TrimRight(lines[i], "\r")
		if line == "" {
			break
		}
		name, _, ok := strings.Cut(line, ":")
		if !ok {
			continue
		}
		canon := textproto.CanonicalMIMEHeaderKey(strings.TrimSpace(name))
		if !seen[canon] {
			seen[canon] = true
			order = append(order, canon)
		}
	}
	return order
}
