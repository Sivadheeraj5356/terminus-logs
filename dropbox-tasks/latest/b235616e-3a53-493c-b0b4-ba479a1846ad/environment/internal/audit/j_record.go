package audit

import (
	"encoding/json"
	"fmt"
	"os"

	"baylock/internal/config"
	"baylock/internal/domain"
	"baylock/internal/projection"
)

// ResolveActor is unfinished.
func ResolveActor(viewID string) string {
	_ = viewID
	pid := os.Getpid()
	return fmt.Sprintf("host:scope-%d", pid)
}

func nextAuditSeq(rt *domain.Runtime) int {
	if rt.AuditSeq < 0 {
		rt.AuditSeq = 0
	}
	rt.AuditSeq++
	return rt.AuditSeq
}

// WriteAudit is unfinished: actor_ref / view binding is incomplete.
func WriteAudit(rt *domain.Runtime, principal string) {
	seq := nextAuditSeq(rt)
	rt.Audits = append(rt.Audits, domain.AuditRecord{
		ViewID:    domain.ViewHost,
		Principal: principal,
		ActorRef:  ResolveActor(rt.ActiveView),
		Seq:       seq,
	})
}

// WriteTrail is unfinished: digests and batch provenance are not computed yet.
func WriteTrail(path string) error {
	snap, err := projection.Load()
	if err != nil {
		snap = &projection.Snapshot{GeneratedFrom: domain.GeneratedFrom}
	}
	trail := domain.AuditTrail{
		GeneratedFrom:    domain.AuditGeneratedFrom,
		BatchCount:       0,
		ProjectionDigest: snap.ProjectionDigest,
		Batches:          []map[string]any{},
	}
	data, err := json.MarshalIndent(trail, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	if err := os.MkdirAll(config.OutputDir, 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, data, 0o644)
}
