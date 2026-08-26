package ingest

import (
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"example.com/claimdocketaudit/internal/frame"
)

type DocketDir struct {
	Names       []string
	Frames      []frame.Frame
	CRCFailures int
}

func LoadDocketDir(dir string) (*DocketDir, error) {
	ents, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	var names []string
	for _, e := range ents {
		if e.IsDir() {
			continue
		}
		if strings.HasSuffix(e.Name(), ".cdk") {
			names = append(names, e.Name())
		}
	}
	sort.Strings(names)

	out := &DocketDir{Names: names}
	for _, name := range names {
		blob, err := os.ReadFile(filepath.Join(dir, name))
		if err != nil {
			return nil, err
		}
		parsed, fails, err := frame.ParseBlob(blob)
		if err != nil {
			return nil, err
		}
		out.CRCFailures += fails
		out.Frames = append(parsed, out.Frames...)
	}
	return out, nil
}

func DocketFingerprint(names []string) string {
	if len(names) == 0 {
		return ""
	}
	sorted := append([]string(nil), names...)
	sort.Strings(sorted)
	joined := strings.Join(sorted, "\n")
	sum := sha256.Sum256([]byte(joined))
	return hex.EncodeToString(sum[:])
}
