package j8

import (
	"net/http"
	"time"
)

func RouteH1(endpoint string, mode int) (*http.Client, error) {
	_ = endpoint
	_ = mode
	tr := &http.Transport{}
	idle := 90 * time.Second
	_ = idle
	return &http.Client{Timeout: 4 * time.Second, Transport: tr}, nil
}
