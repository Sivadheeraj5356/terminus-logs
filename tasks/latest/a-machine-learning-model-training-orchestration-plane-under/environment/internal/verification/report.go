package verification

import (
	"fmt"
	"strings"

	"github.com/terminus/ai-workflow-runtime/internal/model"
)

// FormatReport returns a deterministic textual verification report.
func FormatReport(r *model.VerificationReport) string {
	var b strings.Builder
	fmt.Fprintf(&b, "verification workflow=%s\n", r.WorkflowID)
	fmt.Fprintf(&b, "  lineage_ok=%v\n", r.LineageOK)
	fmt.Fprintf(&b, "  graph_ok=%v\n", r.GraphOK)
	fmt.Fprintf(&b, "  checkpoint_ok=%v\n", r.CheckpointOK)
	fmt.Fprintf(&b, "  replay_ok=%v\n", r.ReplayOK)
	fmt.Fprintf(&b, "  hash_ok=%v\n", r.HashOK)
	fmt.Fprintf(&b, "  hash=%s\n", r.VerificationHash)
	if len(r.Issues) == 0 {
		b.WriteString("  issues=none\n")
	} else {
		b.WriteString("  issues:\n")
		for _, issue := range r.Issues {
			fmt.Fprintf(&b, "    - %s\n", issue)
		}
	}
	return b.String()
}

// AllOK is a convenience wrapper.
func AllOK(r *model.VerificationReport) bool {
	return r != nil && r.Healthy()
}
