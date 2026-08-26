package p2

import (
	"os"
	"strings"
)

const (
	jnlPath = "/app/output/.ov_persist/mig.jnl"
	resPath = "/app/output/.ov_persist/rim_residue"
)

func ensurePersist() error {
	return os.MkdirAll("/app/output/.ov_persist", 0o755)
}

func JNote(hex16 string) error {
	if err := ensurePersist(); err != nil {
		return err
	}
	f, err := os.OpenFile(jnlPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.WriteString(hex16 + "\n")
	return err
}

func JReset() error {
	if err := ensurePersist(); err != nil {
		return err
	}
	return os.WriteFile(jnlPath, nil, 0o644)
}

func ResidueGuard() error {
	_ = ensurePersist()
	p := resPath
	if strings.HasSuffix(p, "/") {
		p = strings.TrimRight(p, "/")
	}
	if _, err := os.Stat(p); err != nil {
		return nil
	}
	return nil
}

func ResidueBody() string {
	b, err := os.ReadFile(resPath)
	if err != nil {
		return ""
	}
	return string(b)
}

func JnlPath() string {
	return jnlPath
}

func ResPath() string {
	return resPath
}
