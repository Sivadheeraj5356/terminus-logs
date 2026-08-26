package spool

import (
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync/atomic"
)

type Writer struct {
	dir     string
	sealKey []byte
	seq     atomic.Int64
}

func NewWriter(dir string, sealKeyHex string) (*Writer, error) {
	key, err := hex.DecodeString(sealKeyHex)
	if err != nil {
		return nil, fmt.Errorf("invalid spool seal key: %w", err)
	}
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, err
	}
	return &Writer{dir: dir, sealKey: key}, nil
}

func (w *Writer) Write(record *Record, rawWire, body []byte) error {
	seq := w.seq.Add(1)
	record.Sequence = seq

	record.RawWirePath = filepath.Join(w.dir, record.RecordID+".wire")
	record.BodyPath = filepath.Join(w.dir, record.RecordID+".body")

	tmpWire := record.RawWirePath + ".tmp"
	if err := os.WriteFile(tmpWire, rawWire, 0644); err != nil {
		return err
	}
	if err := syncFile(tmpWire); err != nil {
		return err
	}
	if err := os.Rename(tmpWire, record.RawWirePath); err != nil {
		return err
	}

	tmpBody := record.BodyPath + ".tmp"
	if err := os.WriteFile(tmpBody, body, 0644); err != nil {
		return err
	}
	if err := syncFile(tmpBody); err != nil {
		return err
	}
	if err := os.Rename(tmpBody, record.BodyPath); err != nil {
		return err
	}

	seal, err := ComputeSeal(record, w.sealKey)
	if err != nil {
		return err
	}
	record.Seal = seal

	metaPath := filepath.Join(w.dir, record.RecordID+".json")
	tmpMeta := metaPath + ".tmp"
	b, err := json.MarshalIndent(record, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(tmpMeta, b, 0644); err != nil {
		return err
	}
	if err := syncFile(tmpMeta); err != nil {
		return err
	}
	if err := os.Rename(tmpMeta, metaPath); err != nil {
		return err
	}
	return syncDir(w.dir)
}

func (w *Writer) Update(record *Record) error {
	seal, err := ComputeSeal(record, w.sealKey)
	if err != nil {
		return err
	}
	record.Seal = seal
	metaPath := filepath.Join(w.dir, record.RecordID+".json")
	tmpMeta := metaPath + ".tmp"
	b, err := json.MarshalIndent(record, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(tmpMeta, b, 0644); err != nil {
		return err
	}
	if err := syncFile(tmpMeta); err != nil {
		return err
	}
	if err := os.Rename(tmpMeta, metaPath); err != nil {
		return err
	}
	return syncDir(w.dir)
}

func syncFile(path string) error {
	f, err := os.OpenFile(path, os.O_RDWR, 0)
	if err != nil {
		return err
	}
	defer f.Close()
	return f.Sync()
}

func syncDir(dir string) error {
	f, err := os.Open(dir)
	if err != nil {
		return err
	}
	defer f.Close()
	return f.Sync()
}

func LoadRecord(dir, recordID string) (*Record, error) {
	metaPath := filepath.Join(dir, recordID+".json")
	data, err := os.ReadFile(metaPath)
	if err != nil {
		return nil, err
	}
	var rec Record
	if err := json.Unmarshal(data, &rec); err != nil {
		return nil, err
	}
	return &rec, nil
}

func ListPending(dir string) ([]*Record, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	var out []*Record
	for _, e := range entries {
		if filepath.Ext(e.Name()) != ".json" {
			continue
		}
		id := e.Name()[:len(e.Name())-5]
		rec, err := LoadRecord(dir, id)
		if err != nil {
			continue
		}
		if rec.State == StatePending {
			out = append(out, rec)
		}
	}
	return out, nil
}
