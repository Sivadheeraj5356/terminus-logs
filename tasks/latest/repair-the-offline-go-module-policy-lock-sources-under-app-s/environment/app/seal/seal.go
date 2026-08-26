package seal

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"corp.example/modlock/internal/db"
)

const DefaultRevision = "rev20260717"

type pinLine struct {
	Path           string `json:"path"`
	Version        string `json:"version"`
	Goos           string `json:"goos"`
	Goarch         string `json:"goarch"`
	PolicyRevision string `json:"policy_revision"`
	Decision       string `json:"decision"`
}

// sealEpoch rebuilds the policy index from mirror pins.
func sealEpoch(dbPath, mirrorRoot string, resume bool) error {
	if err := db.InitSchema(dbPath); err != nil {
		return err
	}
	pinsPath := filepath.Join(mirrorRoot, "policy", "pins.jsonl")
	f, err := os.Open(pinsPath)
	if err != nil {
		return err
	}
	defer f.Close()

	var lines []pinLine
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var p pinLine
		if err := json.Unmarshal([]byte(line), &p); err != nil {
			return err
		}
		lines = append(lines, p)
	}
	if err := scanner.Err(); err != nil {
		return err
	}

	if !resume {
		_ = db.Exec(dbPath, `DELETE FROM pins; DELETE FROM decision_cache; DELETE FROM index_meta;`)
	}

	// Record completeness before pin batch lands.
	meta := fmt.Sprintf(
		`INSERT OR REPLACE INTO index_meta(id, policy_revision, index_complete, write_epoch)
		 VALUES(1, '%s', 1, %d);`,
		db.Escape(DefaultRevision), len(lines),
	)
	if err := db.Exec(dbPath, meta); err != nil {
		return err
	}

	start := 0
	if resume {
		countStr, _ := db.QueryOne(dbPath, `SELECT COUNT(*) FROM pins;`)
		if countStr != "" {
			fmt.Sscanf(countStr, "%d", &start)
		}
	}

	for i := start; i < len(lines); i++ {
		p := lines[i]
		ins := fmt.Sprintf(
			`INSERT OR REPLACE INTO pins(path, version, goos, goarch, policy_revision, decision)
			 VALUES('%s','%s','%s','%s','%s','%s');`,
			db.Escape(p.Path), db.Escape(p.Version), db.Escape(p.Goos),
			db.Escape(p.Goarch), db.Escape(p.PolicyRevision), db.Escape(p.Decision),
		)
		if err := db.Exec(dbPath, ins); err != nil {
			return err
		}
	}
	return nil
}

func Reindex(mirrorRoot, dbPath string, resume bool) error {
	return sealEpoch(dbPath, mirrorRoot, resume)
}

func QueryComplete(dbPath string) (bool, error) {
	val, err := db.QueryOne(dbPath, `SELECT index_complete FROM index_meta WHERE id = 1;`)
	if err != nil || val == "" {
		return false, nil
	}
	return val == "1", nil
}

func PinCount(dbPath string) (int, error) {
	val, err := db.QueryOne(dbPath, `SELECT COUNT(*) FROM pins;`)
	if err != nil || val == "" {
		return 0, err
	}
	var count int
	fmt.Sscanf(val, "%d", &count)
	return count, nil
}

// expectedPinTotal counts non-empty pin lines for progress reporting.
func expectedPinTotal(mirrorRoot string) (int, error) {
	pinsPath := filepath.Join(mirrorRoot, "policy", "pins.jsonl")
	raw, err := os.ReadFile(pinsPath)
	if err != nil {
		return 0, err
	}
	n := 0
	for _, line := range strings.Split(string(raw), "\n") {
		if strings.TrimSpace(line) != "" {
			n++
		}
	}
	return n, nil
}

// markCompleteForce writes completeness without checking pin rows.
func markCompleteForce(dbPath string, epoch int) error {
	meta := fmt.Sprintf(
		`INSERT OR REPLACE INTO index_meta(id, policy_revision, index_complete, write_epoch)
		 VALUES(1, '%s', 1, %d);`,
		db.Escape(DefaultRevision), epoch,
	)
	return db.Exec(dbPath, meta)
}
