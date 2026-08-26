package scheduler

import (
	"github.com/terminus/ai-workflow-runtime/internal/model"
)

// ResolveRetries returns effective retry budget for a node.
func ResolveRetries(n model.Node, pol *model.Policy) int {
	if n.MaxRetries > 0 {
		return n.MaxRetries
	}
	return pol.MaxRetries
}

// ResolveTimeout returns effective timeout for a node.
func ResolveTimeout(n model.Node, pol *model.Policy) int {
	if n.TimeoutMs > 0 {
		return n.TimeoutMs
	}
	return pol.TimeoutMs
}
