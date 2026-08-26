package signing

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"zonepub/internal/config"
	"zonepub/internal/nsec3"
)

type Request struct {
	Origin      string
	InputZone   string
	OutputZone  string
	KeysDir     string
	KeyFiles    []string
	Epoch       int64
	Lifetime    int64
	NSEC3       nsec3.Params
	Recovered   bool
	PlanStart   int64
	PlanEnd     int64
}

func Sign(cfg *config.Config, req Request) error {
	start, end := req.PlanStart, req.PlanEnd
	if start == 0 || end == 0 {
		now := time.Now().Unix()
		start = now
		end = now + cfg.SignatureLifetime
	}
	args := []string{
		"-o", req.Origin,
		"-s", fmt.Sprintf("%d", start),
		"-e", fmt.Sprintf("%d", end),
		"-K", req.KeysDir,
		"-P", "-z",
	}
	for _, kf := range req.KeyFiles {
		args = append(args, "-k", filepath.Base(strings.TrimSuffix(kf, ".private")))
	}
	nsecArgs := strings.Fields(req.NSEC3.SignzoneArg())
	if len(nsecArgs) > 0 {
		args = append(args, nsecArgs...)
	}
	args = append(args, req.InputZone)
	logPath := filepath.Join("/logs", "dnssec-signzone.log")
	_ = os.MkdirAll("/logs", 0o755)
	cmd := exec.Command("dnssec-signzone", args...)
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	out, err := cmd.Output()
	if err != nil {
		_ = os.WriteFile(logPath, append(out, stderr.Bytes()...), 0o644)
		return fmt.Errorf("dnssec-signzone: %w: %s", err, stderr.String())
	}
	_ = os.WriteFile(logPath, append(out, stderr.Bytes()...), 0o644)
	signed := req.InputZone + ".signed"
	if err := os.Rename(signed, req.OutputZone); err != nil {
		data, rerr := os.ReadFile(signed)
		if rerr != nil {
			return err
		}
		if werr := os.WriteFile(req.OutputZone, data, 0o644); werr != nil {
			return werr
		}
		_ = os.Remove(signed)
	}
	return nil
}
