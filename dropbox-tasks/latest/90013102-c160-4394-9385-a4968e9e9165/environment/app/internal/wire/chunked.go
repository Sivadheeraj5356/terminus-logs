package wire

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"strconv"
	"strings"
)

func DecodeChunked(body []byte) ([]byte, error) {
	reader := bufio.NewReader(bytes.NewReader(body))
	var out bytes.Buffer
	for {
		line, err := reader.ReadString('\n')
		if err != nil {
			return nil, fmt.Errorf("chunked: read size: %w", err)
		}
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		sizeStr, _, _ := strings.Cut(line, ";")
		size, err := strconv.ParseInt(sizeStr, 16, 64)
		if err != nil {
			return nil, fmt.Errorf("chunked: invalid size %q: %w", sizeStr, err)
		}
		if size == 0 {
			for {
				trailer, err := reader.ReadString('\n')
				if err != nil {
					if err == io.EOF {
						break
					}
					return nil, err
				}
				if strings.TrimSpace(trailer) == "" {
					break
				}
			}
			break
		}
		chunk := make([]byte, size)
		if _, err := io.ReadFull(reader, chunk); err != nil {
			return nil, fmt.Errorf("chunked: read chunk: %w", err)
		}
		if _, err := reader.ReadString('\n'); err != nil {
			return nil, fmt.Errorf("chunked: read chunk trailer: %w", err)
		}
		out.Write(chunk)
	}
	return out.Bytes(), nil
}
