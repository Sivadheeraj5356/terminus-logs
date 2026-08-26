package c7

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"

	"mxbin/a6/b4"
)

var home = map[string]string{"ca": "pH", "cb": "qH", "cc": "tH"}

func Covers(have, need string) bool {
	h, n := b4.ResolveAlias(have), b4.ResolveAlias(need)
	if b4.PrincRank(h) == 0 || b4.PrincRank(n) == 0 {
		return false
	}
	if h[0] != n[0] {
		return false
	}
	return b4.PrincRank(h) >= b4.PrincRank(n)
}

func loadEff(scratch string) (map[string]b4.Row, error) {
	path := filepath.Join(scratch, "eff.rows")
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	out := map[string]b4.Row{}
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		p := strings.Fields(line)
		if len(p) < 4 {
			continue
		}
		g, _ := strconv.Atoi(p[3])
		touch := 0
		if len(p) >= 5 {
			touch, _ = strconv.Atoi(p[4])
		}
		out[p[0]] = b4.Row{ID: p[0], Cloud: p[1], Actor: p[2], Gen: g, Touch: touch}
	}
	return out, sc.Err()
}

func cutFloor(sign string) int {
	raw, err := os.ReadFile(filepath.Join(sign, "meta", "cut.cfg"))
	if err != nil {
		return 0
	}
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "cut_floor=") {
			v, _ := strconv.Atoi(strings.TrimPrefix(line, "cut_floor="))
			return v
		}
	}
	return 0
}

func quorumMin(sign string) int {
	raw, err := os.ReadFile(filepath.Join(sign, "meta", "quorum.cfg"))
	if err != nil {
		return 1
	}
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "min_touches=") {
			v, _ := strconv.Atoi(strings.TrimPrefix(line, "min_touches="))
			return v
		}
	}
	return 1
}

func loadCertWindows(sign string) map[string][2]int {
	out := map[string][2]int{}
	raw, err := os.ReadFile(filepath.Join(sign, "certs.d", "windows.crt"))
	if err != nil {
		return out
	}
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		p := strings.Fields(line)
		if len(p) < 3 {
			continue
		}
		nb, _ := strconv.Atoi(p[1])
		na, _ := strconv.Atoi(p[2])
		out[p[0]] = [2]int{nb, na}
	}
	return out
}

func loadLogTimes(sign string) map[string]int {
	out := map[string]int{}
	raw, err := os.ReadFile(filepath.Join(sign, "log.d", "times.jnl"))
	if err != nil {
		return out
	}
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		p := strings.Fields(line)
		if len(p) < 2 {
			continue
		}
		t, _ := strconv.Atoi(p[1])
		out[p[0]] = t
	}
	return out
}

func certOK(id string, certs map[string][2]int, times map[string]int) bool {
	w, ok := certs[id]
	if !ok {
		return false
	}
	t, ok := times[id]
	if !ok {
		return false
	}
	return t >= w[0] && t <= w[1]
}

// BindBroken admits any non-poison actor; ignores cut/cert/quorum.
func BindBroken(eff map[string]b4.Row, sign string) map[string]b4.Row {
	_ = sign
	out := map[string]b4.Row{}
	for id, r := range eff {
		actor := b4.ResolveAlias(r.Actor)
		if actor != "" && b4.PrincRank(actor) > 0 {
			r.Actor = actor
			out[id] = r
		}
	}
	return out
}

// BindCorrect applies home lattice + cut floor + cert window + quorum touches.
func BindCorrect(eff map[string]b4.Row, sign string) map[string]b4.Row {
	cut := cutFloor(sign)
	qmin := quorumMin(sign)
	certs := loadCertWindows(sign)
	times := loadLogTimes(sign)
	out := map[string]b4.Row{}
	for id, r := range eff {
		actor := b4.ResolveAlias(r.Actor)
		if actor != home[r.Cloud] {
			continue
		}
		if r.Gen < cut {
			continue
		}
		if r.Touch < qmin {
			continue
		}
		if !certOK(id, certs, times) {
			continue
		}
		r.Actor = actor
		out[id] = r
	}
	return out
}

func writeBound(outPath string, bound map[string]b4.Row, scratch string) error {
	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		return err
	}
	ids := make([]string, 0, len(bound))
	for id := range bound {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	var b strings.Builder
	for _, id := range ids {
		r := bound[id]
		fmt.Fprintf(&b, "%s|%s|%s|%d|H\n", r.ID, r.Cloud, r.Actor, r.Gen)
	}
	if err := os.WriteFile(outPath, []byte(b.String()), 0o644); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(scratch, "bound.meta"), []byte("fx=0\n"), 0o644)
}

func Freshness(bound map[string]b4.Row, xdir string) ([]map[string]any, []map[string]string, error) {
	entries, err := os.ReadDir(xdir)
	if err != nil {
		return nil, nil, err
	}
	var fresh []map[string]any
	var classify []map[string]string
	names := []string{}
	for _, e := range entries {
		if strings.HasSuffix(e.Name(), ".yaml") {
			names = append(names, e.Name())
		}
	}
	sort.Strings(names)
	for _, name := range names {
		rid, span, minG, leaves, err := parseXrow(filepath.Join(xdir, name))
		if err != nil {
			return nil, nil, err
		}
		touch := 0
		genN := 0
		for _, leaf := range leaves {
			row, ok := bound[leaf[0]]
			if !ok {
				continue
			}
			if row.Gen < minG {
				continue
			}
			if !Covers(row.Actor, leaf[1]) {
				continue
			}
			touch++
			genN += row.Gen
		}
		skew := touch - span
		if skew < 0 {
			skew = -skew
		}
		fresh = append(fresh, map[string]any{
			"id": rid, "skew": skew, "gen_n": genN, "span": span, "touch": touch,
		})
		band := "drift"
		if skew == 0 {
			band = "steady"
		}
		classify = append(classify, map[string]string{"id": rid, "band": band})
	}
	return fresh, classify, nil
}

func parseXrow(path string) (string, int, int, [][2]string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return "", 0, 0, nil, err
	}
	rid := strings.TrimSuffix(filepath.Base(path), ".yaml")
	span, minG := 0, 0
	var leaves [][2]string
	var curID string
	for _, line := range strings.Split(string(raw), "\n") {
		s := strings.TrimSpace(line)
		switch {
		case strings.HasPrefix(s, "span:"):
			span, _ = strconv.Atoi(strings.TrimSpace(strings.TrimPrefix(s, "span:")))
		case strings.HasPrefix(s, "min_g:"):
			minG, _ = strconv.Atoi(strings.TrimSpace(strings.TrimPrefix(s, "min_g:")))
		case strings.HasPrefix(s, "- id:"):
			curID = strings.TrimSpace(strings.TrimPrefix(s, "- id:"))
		case strings.HasPrefix(s, "need:") && curID != "":
			leaves = append(leaves, [2]string{curID, strings.TrimSpace(strings.TrimPrefix(s, "need:"))})
			curID = ""
		}
	}
	return rid, span, minG, leaves, nil
}

func WriteFresh(scratch string, fresh []map[string]any) error {
	var b strings.Builder
	for _, r := range fresh {
		fmt.Fprintf(&b, "id:%s skew:%v gen_n:%v span:%v touch:%v\n",
			r["id"], r["skew"], r["gen_n"], r["span"], r["touch"])
	}
	return os.WriteFile(filepath.Join(scratch, "fresh.rows"), []byte(b.String()), 0o644)
}
