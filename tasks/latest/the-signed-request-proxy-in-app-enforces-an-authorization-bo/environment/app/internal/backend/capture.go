package backend

import (
	"bufio"
	"bytes"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net"
	"net/textproto"
	"os"
	"sync"
)

type CapturedRequest struct {
	Method      string            `json:"method"`
	Target      string            `json:"target"`
	Headers     map[string]string `json:"headers"`
	Body        string            `json:"body"`
	BodyHex     string            `json:"body_hex,omitempty"`
	RawDigest   string            `json:"raw_digest"`
	ReceivedAt  string            `json:"received_at"`
}

var (
	captureMu sync.Mutex
	lastCapture CapturedRequest
	capturePath string
)

func SetCapturePath(path string) {
	capturePath = path
}

func LastCapture() CapturedRequest {
	captureMu.Lock()
	defer captureMu.Unlock()
	return lastCapture
}

func ServeCapture(unixPath string, outputPath string) error {
	capturePath = outputPath
	_ = os.Remove(unixPath)
	ln, err := net.Listen("unix", unixPath)
	if err != nil {
		return err
	}
	for {
		conn, err := ln.Accept()
		if err != nil {
			return err
		}
		go handleCapture(conn)
	}
}

func handleCapture(conn net.Conn) {
	defer conn.Close()
	reader := bufio.NewReader(conn)
	reqLine, err := reader.ReadString('\n')
	if err != nil {
		return
	}
	tp := textproto.NewReader(reader)
	mh, err := tp.ReadMIMEHeader()
	if err != nil {
		return
	}
	var contentLen int
	if cl := mh.Get("Content-Length"); cl != "" {
		fmt.Sscanf(cl, "%d", &contentLen)
	}
	body := make([]byte, contentLen)
	if contentLen > 0 {
		_, _ = reader.Read(body)
	}
	headers := make(map[string]string)
	for k := range mh {
		headers[textproto.CanonicalMIMEHeaderKey(k)] = mh.Get(k)
	}
	parts := bytes.Fields([]byte(reqLine))
	method, target := "", ""
	if len(parts) >= 2 {
		method = string(parts[0])
		target = string(parts[1])
	}
	cap := CapturedRequest{
		Method:  method,
		Target:  target,
		Headers: headers,
		Body:    string(body),
		BodyHex: hex.EncodeToString(body),
	}
	captureMu.Lock()
	lastCapture = cap
	captureMu.Unlock()
	if capturePath != "" {
		b, _ := json.MarshalIndent(cap, "", "  ")
		_ = os.WriteFile(capturePath, b, 0644)
	}
	resp := "HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK"
	_, _ = conn.Write([]byte(resp))
}
