package proxy

import (
	"fmt"
	"net"
)

func BackendReachable(backendUnix string) bool {
	conn, err := net.Dial("unix", backendUnix)
	if err != nil {
		return false
	}
	conn.Close()
	return true
}

type RetryDecision struct {
	Queue   bool
	Reason  string
	ImmediateReject bool
}

func DecideRetry(backendUnix string, authorized bool) RetryDecision {
	if !authorized {
		return RetryDecision{Queue: false, ImmediateReject: true, Reason: "unauthorized"}
	}
	if BackendReachable(backendUnix) {
		return RetryDecision{Queue: false, Reason: "backend_online"}
	}
	return RetryDecision{Queue: true, Reason: "backend_offline"}
}

func RetryResponse() []byte {
	body := `{"status":"queued","message":"request spooled for retry"}`
	return []byte(fmt.Sprintf("HTTP/1.1 202 Accepted\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n%s", len(body), body))
}

func RejectResponse(reason string) []byte {
	body := fmt.Sprintf(`{"status":"rejected","reason":"%s"}`, reason)
	return []byte(fmt.Sprintf("HTTP/1.1 401 Unauthorized\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n%s", len(body), body))
}

func ErrorResponse(status int, reason string) []byte {
	body := fmt.Sprintf(`{"status":"error","reason":"%s"}`, reason)
	return []byte(fmt.Sprintf("HTTP/1.1 %d \r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n%s", status, len(body), body))
}
