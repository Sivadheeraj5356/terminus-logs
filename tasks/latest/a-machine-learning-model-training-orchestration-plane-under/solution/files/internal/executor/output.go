package executor

import (
	"fmt"
	"strings"

	"github.com/terminus/ai-workflow-runtime/internal/hash"
	"github.com/terminus/ai-workflow-runtime/internal/model"
)

// SummarizeResults builds a deterministic human-readable execution summary.
func SummarizeResults(rec *model.ExecutionRecord) string {
	var b strings.Builder
	fmt.Fprintf(&b, "workflow=%s status=%s journal=%s\n", rec.WorkflowID, rec.Status, rec.JournalHash)
	results := append([]model.NodeResult{}, rec.Results...)
	// already sorted by caller usually; ensure
	for i := 0; i < len(results); i++ {
		for j := i + 1; j < len(results); j++ {
			if results[j].NodeID < results[i].NodeID {
				results[i], results[j] = results[j], results[i]
			}
		}
	}
	for _, r := range results {
		fmt.Fprintf(&b, "  %s status=%s attempts=%d worker=%s digest=%s\n",
			r.NodeID, r.Status, r.Attempts, r.WorkerID, r.Digest)
	}
	return b.String()
}

// AggregateDigest binds all node digests.
func AggregateDigest(rec *model.ExecutionRecord) string {
	var b strings.Builder
	b.WriteString(rec.WorkflowID)
	b.WriteByte('\n')
	results := append([]model.NodeResult{}, rec.Results...)
	for i := 0; i < len(results); i++ {
		for j := i + 1; j < len(results); j++ {
			if results[j].NodeID < results[i].NodeID {
				results[i], results[j] = results[j], results[i]
			}
		}
	}
	for _, r := range results {
		b.WriteString(r.NodeID)
		b.WriteByte(':')
		b.WriteString(r.Digest)
		b.WriteByte(';')
	}
	return hash.DomainHash("exec-aggregate", []byte(b.String()))
}
