package proxy

import (
	"sigproxy/internal/backend"
	"sigproxy/internal/semantics"
)

type ForwardOutcome struct {
	BackendDigest string
	BackendLength int
	StatusCode    int
	ResponseBody  []byte
}

func ForwardSemantic(backendUnix string, sem *semantics.Request) (*ForwardOutcome, error) {
	res, err := backend.ForwardSemantic(backendUnix, sem)
	if err != nil {
		return nil, err
	}
	return &ForwardOutcome{
		BackendDigest: res.BackendDigest,
		BackendLength: res.BackendLength,
		StatusCode:    res.StatusCode,
		ResponseBody:  res.ResponseBody,
	}, nil
}

func PrepareForwardHeaders(sem *semantics.Request, policy semantics.HeaderPolicy) {
	sem.CanonicalHeaders = append([]semantics.HeaderField(nil), sem.CanonicalHeaders...)
}
