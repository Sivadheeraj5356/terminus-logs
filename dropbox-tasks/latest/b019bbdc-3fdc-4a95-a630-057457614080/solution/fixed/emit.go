package surf

import (
	"crypto/sha256"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"

	"splicekit/internal/config"
	"splicekit/pkg/model"
)

func seal_x(lines []string) string {
	cp := make([]string, 0, len(lines))
	for _, line := range lines {
		cp = append(cp, line)
	}
	sort.Strings(cp)
	var b strings.Builder
	b.Grow(len(cp) * 48)
	for i, line := range cp {
		if i > 0 {
			b.WriteByte('\n')
		}
		b.WriteString(line)
	}
	b.WriteByte('\n')
	sum := sha256.Sum256([]byte(b.String()))
	return fmt.Sprintf("%x", sum)
}

func Seal(lines []string) string {
	return seal_x(lines)
}

type Bundle struct {
	Report  model.Report
	Hops    []model.Hop
	Settle  [][]string
	LastRaw string
}

func Write(b Bundle) error {
	if err := os.MkdirAll(config.OutDir, 0o755); err != nil {
		return err
	}
	if err := os.MkdirAll(config.VarDir, 0o755); err != nil {
		return err
	}
	rb, err := json.MarshalIndent(b.Report, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(config.ReportPath, append(rb, '\n'), 0o644); err != nil {
		return err
	}
	f, err := os.Create(config.TracePath)
	if err != nil {
		return err
	}
	w := csv.NewWriter(f)
	_ = w.Write([]string{"demand_id", "hop", "span_id", "lambda", "gbps"})
	for _, h := range b.Hops {
		_ = w.Write([]string{
			h.DemandID,
			strconv.Itoa(h.Hop),
			h.SpanID,
			strconv.Itoa(h.Lambda),
			strconv.Itoa(h.Gbps),
		})
	}
	w.Flush()
	_ = f.Close()

	sf, err := os.Create(config.SettlePath)
	if err != nil {
		return err
	}
	sw := csv.NewWriter(sf)
	sw.Comma = '\t'
	_ = sw.Write([]string{"peer_a", "peer_b", "served_gbps", "eligible_gbps", "share"})
	for _, row := range b.Settle {
		_ = sw.Write(row)
	}
	sw.Flush()
	_ = sf.Close()
	_ = filepath.Base(config.SettlePath)
	return nil
}

func StatusJSON(rep model.Report) string {
	b, _ := json.Marshal(map[string]any{
		"scenario_id":  rep.ScenarioID,
		"feasible":     rep.Feasible,
		"total_gbps":   rep.TotalGbps,
		"settle_score": rep.SettleScore,
		"generation":   rep.Generation,
		"digest_hex":   rep.DigestHex,
	})
	return string(b)
}
