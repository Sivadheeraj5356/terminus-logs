package trace

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sync"

	"sigproxy/internal/audit"
)

type Writer struct {
	path string
	doc  Document
	mu   sync.Mutex
}

func NewWriter(path, runMode, catalogDigest string) *Writer {
	return &Writer{
		path: path,
		doc: Document{
			SchemaVersion: "1.0",
			RunMode:       runMode,
			CatalogDigest: catalogDigest,
			Entries:       make([]Entry, 0),
		},
	}
}

func (w *Writer) AddFromSnapshot(snap *audit.DecisionSnapshot, wireDigest string, entityLen int, forward *ForwardEvidence, spool *SpoolEvidence, auditDigest string) {
	entry := Entry{
		RequestID:        snap.RequestID,
		Source:           snap.Source,
		WireDigest:       wireDigest,
		EntityDigest:     snap.EntityBodySHA256,
		EntityLength:     entityLen,
		Decision:         snap.Decision,
		Reason:           string(snap.Reason),
		SignatureVersion: snap.SignatureVersion,
		Tenant:           snap.Tenant,
		KeyID:            snap.KeyID,
		KeyEpoch:         snap.KeyEpoch,
		ProfileID:        snap.ProfileID,
		ProfileEpoch:     snap.ProfileEpoch,
		CanonicalDigest:  snap.CanonicalDigest,
		CacheHit:         snap.CacheHit,
		Method:           snap.Semantic.Method,
		Authority:        snap.Semantic.Authority,
		CanonicalTarget:  snap.CanonicalTarget,
		CanonicalHeaders: snap.CanonicalHeaders,
		BodySHA256:       snap.EntityBodySHA256,
		BodyLength:       snap.EntityBodyLength,
		Forward:          forward,
		Spool:            spool,
		AuditRecordDigest: auditDigest,
	}
	w.mu.Lock()
	w.doc.Entries = append(w.doc.Entries, entry)
	w.mu.Unlock()
}

func (w *Writer) Flush() error {
	w.mu.Lock()
	defer w.mu.Unlock()
	if err := os.MkdirAll(filepath.Dir(w.path), 0755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(w.doc, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(w.path, b, 0644)
}

func (w *Writer) Document() Document {
	w.mu.Lock()
	defer w.mu.Unlock()
	return w.doc
}
