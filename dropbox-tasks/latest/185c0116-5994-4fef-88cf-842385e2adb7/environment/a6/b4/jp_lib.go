package b4

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

type Row struct {
	ID    string
	Cloud string
	Actor string
	Gen   int
	Touch int
}

var (
	rank = map[string]int{
		"p1": 1, "p2": 2, "pH": 3,
		"q1": 1, "q2": 2, "qH": 3,
		"t1": 1, "t2": 2, "tH": 3,
		"xF": 0, "xG": 0,
	}
	alias = map[string]string{"pX": "p2", "qX": "q2", "tX": "t2"}
)

func ResolveAlias(p string) string {
	if v, ok := alias[p]; ok {
		return v
	}
	return p
}

func PrincRank(p string) int {
	return rank[ResolveAlias(p)]
}

func JoinPrinc(a, b string) string {
	a, b = ResolveAlias(a), ResolveAlias(b)
	if PrincRank(a) >= PrincRank(b) {
		return a
	}
	return b
}

func readRows(path string) (map[string]Row, error) {
	out := map[string]Row{}
	f, err := os.Open(path)
	if err != nil {
		if os.IsNotExist(err) {
			return out, nil
		}
		return nil, err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.Fields(line)
		if len(parts) < 4 {
			continue
		}
		g, _ := strconv.Atoi(parts[3])
		out[parts[0]] = Row{ID: parts[0], Cloud: parts[1], Actor: parts[2], Gen: g}
	}
	return out, sc.Err()
}

func writeEff(scratch string, m map[string]Row) error {
	if err := os.MkdirAll(scratch, 0o755); err != nil {
		return err
	}
	ids := make([]string, 0, len(m))
	for id := range m {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	var b strings.Builder
	for _, id := range ids {
		r := m[id]
		fmt.Fprintf(&b, "%s %s %s %d %d\n", r.ID, r.Cloud, r.Actor, r.Gen, r.Touch)
	}
	if err := os.WriteFile(filepath.Join(scratch, "eff.rows"), []byte(b.String()), 0o644); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(scratch, "eff.meta"), []byte(fmt.Sprintf("n=%d\n", len(m))), 0o644)
}

// FoldBroken is the shipped fold path: overlays first, flat REPLACE, witness merge.
func FoldBroken(sign string) (map[string]Row, error) {
	m, err := readRows(filepath.Join(sign, "core.d", "models.w"))
	if err != nil {
		return nil, err
	}
	ovlDir := filepath.Join(sign, "ovl.d")
	entries, _ := os.ReadDir(ovlDir)
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".ov") {
			continue
		}
		raw, err := os.ReadFile(filepath.Join(ovlDir, e.Name()))
		if err != nil {
			return nil, err
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
			if cur, ok := m[p[0]]; ok {
				cur.Cloud = p[1]
				cur.Actor = p[2]
				m[p[0]] = cur
			}
		}
	}
	sigDir := filepath.Join(sign, "sig.d")
	sx, _ := os.ReadDir(sigDir)
	for _, e := range sx {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".sx") || e.Name() == "manifest.sx" {
			continue
		}
		rows, err := readRows(filepath.Join(sigDir, e.Name()))
		if err != nil {
			return nil, err
		}
		for id, r := range rows {
			m[id] = r
		}
	}
	bumpPath := filepath.Join(sign, "appr.d", "bump.aw")
	if raw, err := os.ReadFile(bumpPath); err == nil {
		for _, line := range strings.Split(string(raw), "\n") {
			line = strings.TrimSpace(line)
			if line == "" || strings.HasPrefix(line, "#") {
				continue
			}
			p := strings.Fields(line)
			if len(p) >= 3 {
				if cur, ok := m[p[0]]; ok {
					cur.Actor = p[1]
					g, _ := strconv.Atoi(p[2])
					cur.Gen = g
					m[p[0]] = cur
				}
			}
		}
	}
	wit, _ := readRows(filepath.Join(sign, "witness", "local.obs"))
	for id, r := range wit {
		m[id] = r
	}
	return m, nil
}

// FoldCorrect implements normative DAG JOIN → bump → epoch overlays with revoke skips.
func FoldCorrect(sign string) (map[string]Row, error) {
	m, err := readRows(filepath.Join(sign, "core.d", "models.w"))
	if err != nil {
		return nil, err
	}
	nodes := map[string][2]string{}
	man := filepath.Join(sign, "sig.d", "manifest.sx")
	raw, err := os.ReadFile(man)
	if err != nil {
		return nil, err
	}
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.Split(line, "|")
		if len(parts) != 3 {
			continue
		}
		nodes[parts[0]] = [2]string{parts[1], parts[2]}
	}
	done := map[string]bool{}
	var expand func(string) error
	expand = func(name string) error {
		if done[name] {
			return nil
		}
		info, ok := nodes[name]
		if !ok {
			return nil
		}
		fileName, parent := info[0], info[1]
		if parent != "-" {
			if err := expand(parent); err != nil {
				return err
			}
		}
		rows, err := readRows(filepath.Join(sign, "sig.d", fileName))
		if err != nil {
			return err
		}
		for id, r := range rows {
			if cur, ok := m[id]; ok {
				cur.Cloud = r.Cloud
				cur.Actor = JoinPrinc(cur.Actor, r.Actor)
				if r.Gen > cur.Gen {
					cur.Gen = r.Gen
				}
				cur.Touch++
				m[id] = cur
			} else {
				r.Touch = 1
				m[id] = r
			}
		}
		done[name] = true
		return nil
	}
	names := make([]string, 0, len(nodes))
	for n := range nodes {
		names = append(names, n)
	}
	sort.Strings(names)
	for _, n := range names {
		if err := expand(n); err != nil {
			return nil, err
		}
	}

	bumpPath := filepath.Join(sign, "appr.d", "bump.aw")
	if raw, err := os.ReadFile(bumpPath); err == nil {
		for _, line := range strings.Split(string(raw), "\n") {
			line = strings.TrimSpace(line)
			if line == "" || strings.HasPrefix(line, "#") {
				continue
			}
			p := strings.Fields(line)
			if len(p) >= 3 {
				if cur, ok := m[p[0]]; ok {
					cur.Actor = p[1]
					g, _ := strconv.Atoi(p[2])
					cur.Gen = g
					m[p[0]] = cur
				}
			}
		}
	}

	floor := 0
	active := []int{}
	if raw, err := os.ReadFile(filepath.Join(sign, "meta", "epochs.cfg")); err == nil {
		for _, line := range strings.Split(string(raw), "\n") {
			line = strings.TrimSpace(line)
			if strings.HasPrefix(line, "floor=") {
				floor, _ = strconv.Atoi(strings.TrimPrefix(line, "floor="))
			} else if strings.HasPrefix(line, "active=") {
				for _, x := range strings.Split(strings.TrimPrefix(line, "active="), ",") {
					x = strings.TrimSpace(x)
					if x == "" {
						continue
					}
					v, _ := strconv.Atoi(x)
					active = append(active, v)
				}
			}
		}
	}
	revoked := map[[2]string]bool{}
	if raw, err := os.ReadFile(filepath.Join(sign, "meta", "revoke.jnl")); err == nil {
		for _, line := range strings.Split(string(raw), "\n") {
			line = strings.TrimSpace(line)
			if line == "" || strings.HasPrefix(line, "#") {
				continue
			}
			if i := strings.LastIndex(line, "@"); i > 0 {
				ep, _ := strconv.Atoi(line[i+1:])
				revoked[[2]string{line[:i], strconv.Itoa(ep)}] = true
			}
		}
	}
	sort.Ints(active)
	for _, e := range active {
		if e < floor {
			continue
		}
		ov := filepath.Join(sign, "ovl.d", fmt.Sprintf("e%d.ov", e))
		raw, err := os.ReadFile(ov)
		if err != nil {
			continue
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
			if revoked[[2]string{p[0], strconv.Itoa(e)}] {
				continue
			}
			if cur, ok := m[p[0]]; ok {
				cur.Cloud = p[1]
				cur.Actor = p[2]
				m[p[0]] = cur
			}
		}
	}
	return m, nil
}
