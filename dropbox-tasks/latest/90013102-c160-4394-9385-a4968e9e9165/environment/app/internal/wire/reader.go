package wire

import (
	"bufio"
	"fmt"
	"io"
	"net"
	"strconv"
	"strings"
)

// ReadFullRequest reads a complete HTTP/1.1 request from a connection.
func ReadFullRequest(conn net.Conn) ([]byte, error) {
	reader := bufio.NewReader(conn)
	var buf []byte
	for {
		line, err := reader.ReadBytes('\n')
		if err != nil {
			return nil, err
		}
		buf = append(buf, line...)
		if len(line) == 2 && line[0] == '\r' && line[1] == '\n' {
			break
		}
		if len(line) == 1 && line[0] == '\n' {
			break
		}
	}

	headerBlock := string(buf)
	transferCoding := headerFieldFirst(headerBlock, "Transfer-Encoding")
	contentLength := headerFieldInt(headerBlock, "Content-Length")

	var body []byte
	if strings.EqualFold(strings.TrimSpace(transferCoding), "chunked") {
		if contentLength >= 0 {
			return nil, fmt.Errorf("conflicting Transfer-Encoding and Content-Length")
		}
		chunkedWire, err := readChunkedWire(reader)
		if err != nil {
			return nil, err
		}
		body, err = DecodeChunked(chunkedWire)
		if err != nil {
			return nil, err
		}
		buf = append(buf, chunkedWire...)
	} else if contentLength > 0 {
		body = make([]byte, contentLength)
		if _, err := io.ReadFull(reader, body); err != nil {
			return nil, err
		}
		buf = append(buf, body...)
	} else if contentLength == 0 {
		// explicit zero-length body
	}

	return buf, nil
}

func headerFieldFirst(headerBlock, name string) string {
	prefix := name + ":"
	for _, line := range strings.Split(headerBlock, "\n") {
		line = strings.TrimRight(line, "\r")
		if len(line) >= len(prefix) && strings.EqualFold(line[:len(prefix)], prefix) {
			return strings.TrimSpace(line[len(prefix):])
		}
	}
	return ""
}

func headerFieldInt(headerBlock, name string) int {
	val := headerFieldFirst(headerBlock, name)
	if val == "" {
		return -1
	}
	var n int
	if _, err := fmt.Sscanf(val, "%d", &n); err != nil {
		return -1
	}
	return n
}

func readChunkedWire(reader *bufio.Reader) ([]byte, error) {
	var wire []byte
	for {
		line, err := reader.ReadBytes('\n')
		if err != nil {
			return nil, err
		}
		wire = append(wire, line...)
		trimmed := strings.TrimSpace(string(line))
		if trimmed == "" {
			continue
		}
		sizeStr, _, _ := strings.Cut(trimmed, ";")
		size, err := strconv.ParseInt(sizeStr, 16, 64)
		if err != nil {
			return nil, fmt.Errorf("chunked: invalid size %q: %w", sizeStr, err)
		}
		if size == 0 {
			for {
				trailer, err := reader.ReadBytes('\n')
				if err != nil {
					if err == io.EOF {
						break
					}
					return nil, err
				}
				wire = append(wire, trailer...)
				if strings.TrimSpace(string(trailer)) == "" {
					break
				}
			}
			break
		}
		chunk := make([]byte, size)
		if _, err := io.ReadFull(reader, chunk); err != nil {
			return nil, err
		}
		wire = append(wire, chunk...)
		crlf, err := reader.ReadBytes('\n')
		if err != nil {
			return nil, err
		}
		wire = append(wire, crlf...)
	}
	return wire, nil
}
