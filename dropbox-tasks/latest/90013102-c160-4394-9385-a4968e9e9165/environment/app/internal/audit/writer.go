package audit

import (
	"encoding/json"
	"os"
	"sync"
	"time"

	"sigproxy/internal/digest"
)

type SnapshotWriter struct {
	path string
	mu   sync.Mutex
}

func NewSnapshotWriter(path string) *SnapshotWriter {
	return &SnapshotWriter{path: path}
}

func (sw *SnapshotWriter) WriteSnapshot(snap *DecisionSnapshot) (string, error) {
	rec := snap.ToRecord()
	rec.Timestamp = time.Now().UTC().Format(time.RFC3339Nano)
	b, err := json.Marshal(rec)
	if err != nil {
		return "", err
	}
	rec.RecordDigest = digest.SHA256(b)
	b, err = json.Marshal(rec)
	if err != nil {
		return "", err
	}
	sw.mu.Lock()
	defer sw.mu.Unlock()
	f, err := os.OpenFile(sw.path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		return "", err
	}
	defer f.Close()
	if _, err := f.Write(append(b, '\n')); err != nil {
		return "", err
	}
	return rec.RecordDigest, nil
}

type Writer struct {
	path string
	mu   sync.Mutex
}

func NewWriter(path string) *Writer {
	return &Writer{path: path}
}

func (w *Writer) Append(rec Record) error {
	rec.Timestamp = time.Now().UTC().Format(time.RFC3339Nano)
	b, err := json.Marshal(rec)
	if err != nil {
		return err
	}
	rec.RecordDigest = digest.SHA256(b)
	b, err = json.Marshal(rec)
	if err != nil {
		return err
	}
	w.mu.Lock()
	defer w.mu.Unlock()
	f, err := os.OpenFile(w.path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.Write(append(b, '\n'))
	return err
}
