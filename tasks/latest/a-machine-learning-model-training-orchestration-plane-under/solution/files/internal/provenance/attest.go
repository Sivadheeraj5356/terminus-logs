package provenance

import (
	"fmt"
	"sort"
	"strings"

	"github.com/terminus/ai-workflow-runtime/internal/hash"
	"github.com/terminus/ai-workflow-runtime/internal/model"
	"github.com/terminus/ai-workflow-runtime/internal/util"
)

// Statement is a signed-ready provenance statement for a workflow run.
type Statement struct {
	WorkflowID   string            `json:"workflow_id"`
	PlanDigest   string            `json:"plan_digest"`
	JournalHash  string            `json:"journal_hash"`
	ReplayHash   string            `json:"replay_hash"`
	NodeDigests  map[string]string `json:"node_digests"`
	AttestDigest string            `json:"attest_digest"`
}

// BuildStatement creates an attestation statement from pipeline artifacts.
func BuildStatement(wf *model.Workflow, plan *model.ExecutionPlan, rec *model.ExecutionRecord, replayHash string) (*Statement, error) {
	digests := map[string]string{}
	for _, r := range rec.Results {
		digests[r.NodeID] = r.Digest
	}
	st := &Statement{
		WorkflowID:  wf.ID,
		PlanDigest:  plan.Digest,
		JournalHash: rec.JournalHash,
		ReplayHash:  replayHash,
		NodeDigests: digests,
	}
	d, err := Digest(st)
	if err != nil {
		return nil, err
	}
	st.AttestDigest = d
	return st, nil
}

// Digest returns DomainHash("attest-v1", canonical statement without attest_digest).
func Digest(st *Statement) (string, error) {
	payload := map[string]any{
		"workflow_id":  st.WorkflowID,
		"plan_digest":  st.PlanDigest,
		"journal_hash": st.JournalHash,
		"replay_hash":  st.ReplayHash,
		"node_digests": st.NodeDigests,
	}
	b, err := util.CanonicalJSON(payload)
	if err != nil {
		return "", err
	}
	return hash.DomainHash("attest-v1", b), nil
}

// FormatHuman returns a deterministic textual attestation.
func FormatHuman(st *Statement) string {
	keys := make([]string, 0, len(st.NodeDigests))
	for k := range st.NodeDigests {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	var b strings.Builder
	b.WriteString("ATTEST workflow=")
	b.WriteString(st.WorkflowID)
	b.WriteString(" plan=")
	b.WriteString(st.PlanDigest)
	b.WriteString(" journal=")
	b.WriteString(st.JournalHash)
	b.WriteString(" replay=")
	b.WriteString(st.ReplayHash)
	b.WriteByte('\n')
	for _, k := range keys {
		fmt.Fprintf(&b, "  node %s digest=%s\n", k, st.NodeDigests[k])
	}
	fmt.Fprintf(&b, "attest=%s\n", st.AttestDigest)
	return b.String()
}
