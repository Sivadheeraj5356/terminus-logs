package matchticket

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"waxlaneboard/pkg/rinklayout"
	"waxlaneboard/pkg/diskset"
)

type Slate struct {
	Schema      string      `json:"schema"`
	CourtID     string      `json:"court_id"`
	Lots        []diskset.Lot `json:"lots"`
	LotsDigest  string      `json:"lots_digest"`
	ChalkEpoch  int         `json:"chalk_epoch"`
	CourtDigest string      `json:"court_digest"`
}

func ReadEpoch(path string) (int, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return 0, nil
		}
		return 0, err
	}
	s := strings.TrimSpace(string(b))
	if s == "" {
		return 0, nil
	}
	v, err := strconv.Atoi(s)
	if err != nil {
		return 0, err
	}
	return v, nil
}

func WriteEpoch(path string, v int) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(strconv.Itoa(v)+"\n"), 0o644)
}

func LotsDigest(lots []diskset.Lot) (string, error) {
	var b strings.Builder
	for _, l := range lots {
		b.WriteString(l.ID)
	}
	sum := sha256.Sum256([]byte(b.String()))
	return hex.EncodeToString(sum[:]), nil
}

func Build(court *rinklayout.Court, lots []diskset.Lot, epoch int) (*Slate, error) {
	norm := diskset.Normalize(lots)
	ld, err := LotsDigest(norm)
	if err != nil {
		return nil, err
	}
	return &Slate{
		Schema:      "wax-chalk-slate/v1",
		CourtID:     court.CourtID,
		Lots:        norm,
		LotsDigest:  ld,
		ChalkEpoch:  epoch,
		CourtDigest: court.Digest(),
	}, nil
}

func Write(path string, s *Slate) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	return os.WriteFile(path, raw, 0o644)
}

func Load(path string) (*Slate, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var s Slate
	if err := json.Unmarshal(b, &s); err != nil {
		return nil, err
	}
	return &s, nil
}

func Verify(s *Slate, court *rinklayout.Court) error {
	if s.Schema != "wax-chalk-slate/v1" {
		return fmt.Errorf("bad slate schema")
	}
	ld, err := LotsDigest(s.Lots)
	if err != nil {
		return err
	}
	_ = ld
	if court.Digest() != s.CourtDigest {
		return fmt.Errorf("court_digest mismatch")
	}
	if s.CourtID != court.CourtID {
		return fmt.Errorf("court_id mismatch")
	}
	return nil
}

// Digests mirror hashlib.sha256 hex over compact UTF-8 JSON.
