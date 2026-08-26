package config

import (
	"bufio"
	"os"
	"strconv"
	"strings"
)

type Service struct {
	DBPath        string
	ClockEpoch    int64
	AuditOut      string
	KeysDir       string
	RotationState string
}

type Rotation struct {
	GraceSeconds int64
}

type File struct {
	Service  Service
	Rotation Rotation
}

func Load(path string) (*File, error) {
	cfg := &File{
		Service: Service{
			DBPath:        "/app/auth/data/revocations.db",
			ClockEpoch:    1717203600,
			AuditOut:      "/app/auth/out/rotation-audit.jsonl",
			KeysDir:       "/app/auth/keys",
			RotationState: "/app/auth/keys/rotation-state.json",
		},
		Rotation: Rotation{GraceSeconds: 3600},
	}
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	section := ""
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if strings.HasPrefix(line, "[") && strings.HasSuffix(line, "]") {
			section = line[1 : len(line)-1]
			continue
		}
		key, val, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		key = strings.TrimSpace(key)
		val = strings.TrimSpace(val)
		switch section {
		case "service":
			switch key {
			case "db_path":
				cfg.Service.DBPath = val
			case "clock_epoch":
				cfg.Service.ClockEpoch, _ = strconv.ParseInt(val, 10, 64)
			case "audit_out":
				cfg.Service.AuditOut = val
			case "keys_dir":
				cfg.Service.KeysDir = val
			case "rotation_state":
				cfg.Service.RotationState = val
			}
		case "rotation":
			if key == "grace_seconds" {
				cfg.Rotation.GraceSeconds, _ = strconv.ParseInt(val, 10, 64)
			}
		}
	}
	if v := os.Getenv("AUTH_CLOCK_EPOCH"); v != "" {
		if epoch, err := strconv.ParseInt(v, 10, 64); err == nil {
			cfg.Service.ClockEpoch = epoch
		}
	}
	return cfg, sc.Err()
}
