package policy

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"corp.example/modlock/internal/db"
)

type Lookup struct {
	dbPath string
}

func Open(dbPath string) *Lookup {
	return &Lookup{dbPath: dbPath}
}

func (l *Lookup) Revision() (string, error) {
	rev, err := db.QueryOne(l.dbPath, `SELECT policy_revision FROM index_meta WHERE id = 1;`)
	if err != nil || rev == "" {
		return "", fmt.Errorf("policy index not initialized")
	}
	return rev, nil
}

func (l *Lookup) IsComplete() (bool, error) {
	val, err := db.QueryOne(l.dbPath, `SELECT index_complete FROM index_meta WHERE id = 1;`)
	if err != nil || val == "" {
		return false, nil
	}
	return val == "1", nil
}

func (l *Lookup) Pin(path, goos, goarch, policyRevision string) (version, decision string, ok bool, err error) {
	q := fmt.Sprintf(
		`SELECT version || '|' || decision FROM pins WHERE path = '%s' AND goos = '%s' AND goarch = '%s' AND policy_revision = '%s' LIMIT 1;`,
		db.Escape(path), db.Escape(goos), db.Escape(goarch), db.Escape(policyRevision),
	)
	out, err := db.QueryOne(l.dbPath, q)
	if err != nil || out == "" {
		return "", "", false, nil
	}
	parts := strings.SplitN(out, "|", 2)
	if len(parts) != 2 {
		return "", "", false, nil
	}
	return parts[0], parts[1], true, nil
}

func (l *Lookup) MirrorDefault(mirrorRoot, path string) (version string, ok bool) {
	ver := "v1.0.0"
	listPath := filepath.Join(mirrorRoot, "cache/download", path, "@v/list")
	if raw, err := os.ReadFile(listPath); err == nil {
		for _, line := range strings.Split(string(raw), "\n") {
			line = strings.TrimSpace(line)
			if line != "" {
				ver = line
				break
			}
		}
	}
	infoPath := filepath.Join(mirrorRoot, "cache/download", path, "@v", ver+".info")
	raw, err := os.ReadFile(infoPath)
	if err != nil {
		return "", false
	}
	for _, line := range strings.Split(string(raw), "\n") {
		if strings.HasPrefix(line, "Version: ") {
			return strings.TrimPrefix(line, "Version: "), true
		}
	}
	return ver, true
}

func Unauthorized(msg string) {
	fmt.Fprintln(os.Stderr, msg)
	os.Exit(23)
}

const UnauthorizedToken = "unauthorized or missing module"
