#!/usr/bin/env bash
# Bring the lb_drive pipeline modules onto the documented contracts, rebuild,
# and regenerate every arm through the normal reload path.
set -euo pipefail

env_root=/app/environment
out=/app/output/haproxy_route_audit.json

cat > "$env_root/fyn/cord_weft.go" <<'EOF'
package fyn

import "sort"

type packKey struct {
	Kind   string
	Target string
}

// cord_weft folds candidate rows into packed lanes for the active arm.
func cord_weft(rows []LaneRow, seq uint64) []LaneRow {
	type acc struct {
		row  LaneRow
		seen map[string]struct{}
	}
	var never []LaneRow
	var order []packKey
	packs := map[packKey]*acc{}
	for _, r := range rows {
		if r.Want == "deny" {
			m := ""
			if len(r.Match) > 0 {
				m = r.Match[0]
			}
			never = append(never, LaneRow{
				Kind:  r.Kind,
				Match: []string{m},
				Want:  "deny",
				Mode:  "never",
				Seq:   seq,
			})
			continue
		}
		k := packKey{Kind: r.Kind, Target: r.Target}
		a, ok := packs[k]
		if !ok {
			a = &acc{
				row: LaneRow{
					Kind:   r.Kind,
					Target: r.Target,
					Want:   r.Want,
					Mode:   "always",
					Seq:    seq,
				},
				seen: map[string]struct{}{},
			}
			packs[k] = a
			order = append(order, k)
		}
		for _, m := range r.Match {
			if m == "" {
				continue
			}
			if _, hit := a.seen[m]; hit {
				continue
			}
			a.seen[m] = struct{}{}
			a.row.Match = append(a.row.Match, m)
		}
	}
	sort.Slice(never, func(i, j int) bool {
		if never[i].Kind != never[j].Kind {
			return never[i].Kind < never[j].Kind
		}
		return never[i].Match[0] < never[j].Match[0]
	})
	sort.Slice(order, func(i, j int) bool {
		if order[i].Kind != order[j].Kind {
			return order[i].Kind < order[j].Kind
		}
		return order[i].Target < order[j].Target
	})
	out := append([]LaneRow(nil), never...)
	for _, k := range order {
		a := packs[k]
		sort.Strings(a.row.Match)
		out = append(out, a.row)
	}
	return out
}
EOF

cat > "$env_root/jor/gate_tally.go" <<'EOF'
package jor

import (
	"fmt"

	"qxhub/fyn"
)

// gate_tally assigns shared group keys and checks published row/group ceilings.
func gate_tally(rows []fyn.LaneRow, cells []CellSpec, rowCap, groupCap int) ([]fyn.LaneRow, error) {
	_ = cells
	out := append([]fyn.LaneRow(nil), rows...)
	distinct := map[string]struct{}{}
	for i := range out {
		if out[i].Mode == "never" {
			out[i].Group = ""
			out[i].Key = ""
			continue
		}
		key := "g_" + out[i].Kind + "_" + out[i].Target
		out[i].Group = key
		out[i].Key = key
		distinct[key] = struct{}{}
	}
	if rowCap > 0 && len(out) > rowCap {
		return nil, fmt.Errorf("row ceiling: %d rows over cap %d", len(out), rowCap)
	}
	if groupCap > 0 && len(distinct) > groupCap {
		return nil, fmt.Errorf("group ceiling: %d keys over cap %d", len(distinct), groupCap)
	}
	return out, nil
}
EOF

cat > "$env_root/pex/helm_bind.go" <<'EOF'
package pex

import (
	"qxhub/fyn"
	"qxhub/jor"
)

// helm_bind binds rows to published targets and seals outcomes.
func helm_bind(rows []fyn.LaneRow, cells []jor.CellSpec) []CellOut {
	var outs []CellOut
	for _, c := range cells {
		outcome := "miss"
		target := ""
		group := ""
		for _, r := range rows {
			if !rowCovers(r, c) {
				continue
			}
			if r.Mode == "never" {
				outcome = "deny"
				target = ""
				group = ""
			} else {
				outcome = "hit"
				target = r.Target
				group = r.Group
			}
			break
		}
		outs = append(outs, CellOut{ID: c.ID, Outcome: outcome, Target: target, Group: group})
	}
	return outs
}

func rowCovers(r fyn.LaneRow, c jor.CellSpec) bool {
	if r.Kind != c.Kind {
		return false
	}
	for _, m := range r.Match {
		if m == c.Match {
			return true
		}
	}
	return false
}
EOF

cat > "$env_root/pex/pane_seal.go" <<'EOF'
package pex

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
	"strings"

	"qxhub/fyn"
	"qxhub/jor"
)

// pane_seal derives hop records, group keys, and the paired seal digests
// for one arm, then parks them for emit.
func pane_seal(arm string, rows []fyn.LaneRow, cells []jor.CellSpec, outs []CellOut, epoch int) {
	groups := groupList(rows)

	var hops []HopRec
	for _, o := range outs {
		if o.Outcome != "hit" {
			continue
		}
		hops = append(hops, HopRec{ID: o.ID, Cover: "always", Group: o.Group})
	}
	sort.Slice(hops, func(i, j int) bool { return hops[i].ID < hops[j].ID })

	parts := canonParts(arm, rows, outs, groups)
	pane := sealHex(parts)
	twin := sealHex(parts)
	SaveBuf(hops, pane, twin, groups)
	_ = cells
	_ = epoch
}

func groupList(rows []fyn.LaneRow) []string {
	seen := map[string]struct{}{}
	var out []string
	for _, r := range rows {
		if r.Group == "" {
			continue
		}
		if _, ok := seen[r.Group]; ok {
			continue
		}
		seen[r.Group] = struct{}{}
		out = append(out, r.Group)
	}
	sort.Strings(out)
	if out == nil {
		out = []string{}
	}
	return out
}

func canonParts(arm string, rows []fyn.LaneRow, outs []CellOut, groups []string) string {
	var lines []string
	lines = append(lines, "arm="+arm)
	var cellLines []string
	for _, o := range outs {
		cellLines = append(cellLines, fmt.Sprintf("cell:%s=%s:%s:%s", o.ID, o.Outcome, o.Target, o.Group))
	}
	sort.Strings(cellLines)
	lines = append(lines, cellLines...)
	for _, g := range groups {
		lines = append(lines, "group:"+g)
	}
	var rowLines []string
	for _, r := range rows {
		rowLines = append(rowLines, fmt.Sprintf("row:%s|%s|%s|%s", r.Kind, r.Mode, r.Target, strings.Join(r.Match, ",")))
	}
	sort.Strings(rowLines)
	lines = append(lines, rowLines...)
	return strings.Join(lines, "\n") + "\n"
}

func sealHex(text string) string {
	sum := sha256.Sum256([]byte(text))
	return hex.EncodeToString(sum[:])
}
EOF

cat > "$env_root/krv/journal.go" <<'EOF'
package krv

import (
	"encoding/json"
	"os"
	"path/filepath"

	"qxhub/fyn"
	"qxhub/pth"
)

// RecordCut journals an interrupted arm for a later recover pass.
func RecordCut(arm string, rows []fyn.LaneRow) error {
	if err := pth.EnsureDirs(); err != nil {
		return err
	}
	e := Entry{Arm: arm, Pending: len(rows)}
	if len(rows) > 0 && len(rows[0].Match) > 0 {
		e.Hint = rows[0].Match[0]
	}
	raw, err := json.MarshalIndent(e, "", "  ")
	if err != nil {
		return err
	}
	name := filepath.Join(pth.JournalDir(), "cut.jnl")
	return os.WriteFile(name, append(raw, '\n'), 0o644)
}

// Replay consumes any pending cut journal ahead of a recover arm.
func Replay() error {
	if err := pth.EnsureDirs(); err != nil {
		return err
	}
	entries, err := os.ReadDir(pth.JournalDir())
	if err != nil {
		return err
	}
	for _, e := range entries {
		if filepath.Ext(e.Name()) == ".jnl" {
			if err := os.Remove(filepath.Join(pth.JournalDir(), e.Name())); err != nil {
				return err
			}
		}
	}
	if err := os.Remove(pth.LaneShadow()); err != nil && !os.IsNotExist(err) {
		return err
	}
	return nil
}

// HasPending reports whether any cut journal entries remain.
func HasPending() bool {
	entries, err := os.ReadDir(pth.JournalDir())
	if err != nil {
		return false
	}
	for _, e := range entries {
		if filepath.Ext(e.Name()) == ".jnl" {
			return true
		}
	}
	return false
}
EOF

cat > "$env_root/zeb/advance.go" <<'EOF'
package zeb

// Advance moves the durable counters for one completed arm and reseals the anchor.
func Advance(s *Session, kind, arm string) {
	s.ActiveGen++
	switch kind {
	case "cut":
	case "partial":
		s.Epoch++
	case "recover":
		s.Floor = s.ActiveGen - 1
		s.Epoch++
	default:
		s.Floor++
		s.Epoch++
	}
	s.Anchor = SealAnchor(s.ActiveGen, s.Floor, s.Epoch)
	s.LastArm = arm
}
EOF

cat > "$env_root/led/chain.go" <<'EOF'
package led

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"

	"qxhub/pth"
)

// vex_chain appends one committed entry to the durable ledger and returns it.
func vex_chain(gen, floor, epoch int, arm, seal, tx string) (Entry, error) {
	prev := "0"
	if ents, err := readAll(); err == nil && len(ents) > 0 {
		prev = ents[len(ents)-1].Hash
	}
	e := Entry{
		Prev:  prev,
		Gen:   gen,
		Floor: floor,
		Epoch: epoch,
		Arm:   arm,
		Seal:  seal,
		Tx:    tx,
	}
	payload := fmt.Sprintf("%s|%d|%s|%s|%s", e.Prev, e.Gen, e.Arm, e.Seal, e.Tx)
	sum := sha256.Sum256([]byte(payload))
	e.Hash = hex.EncodeToString(sum[:])
	raw, err := json.Marshal(e)
	if err != nil {
		return Entry{}, err
	}
	fh, err := os.OpenFile(pth.LedgerPath(), os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return Entry{}, err
	}
	defer fh.Close()
	if _, err := fh.Write(append(raw, '\n')); err != nil {
		return Entry{}, err
	}
	return e, nil
}

func readAll() ([]Entry, error) {
	fh, err := os.Open(pth.LedgerPath())
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	defer fh.Close()
	var out []Entry
	sc := bufio.NewScanner(fh)
	for sc.Scan() {
		line := sc.Text()
		if line == "" {
			continue
		}
		var e Entry
		if err := json.Unmarshal([]byte(line), &e); err != nil {
			continue
		}
		out = append(out, e)
	}
	return out, sc.Err()
}
EOF

cat > "$env_root/led/mend.go" <<'EOF'
package led

import (
	"encoding/json"
	"os"
	"strings"

	"qxhub/pth"
)

// vex_mend inspects the ledger tail ahead of recover-phase replay or append.
func vex_mend() error {
	raw, err := os.ReadFile(pth.LedgerPath())
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		return err
	}
	text := string(raw)
	if text == "" {
		return nil
	}
	keep := make([]string, 0)
	for _, line := range strings.Split(text, "\n") {
		if strings.TrimSpace(line) == "" {
			continue
		}
		var probe map[string]any
		if json.Unmarshal([]byte(line), &probe) != nil {
			continue
		}
		keep = append(keep, line)
	}
	mended := ""
	if len(keep) > 0 {
		mended = strings.Join(keep, "\n") + "\n"
	}
	if mended == text {
		return nil
	}
	return os.WriteFile(pth.LedgerPath(), []byte(mended), 0o644)
}
EOF

cat > "$env_root/cas/gate.go" <<'EOF'
package cas

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"qxhub/pth"
	"qxhub/zeb"
)

// Mint derives the plan token for one arm at one session generation.
func Mint(arm string, gen int, seal string) (string, error) {
	if err := pth.EnsureDirs(); err != nil {
		return "", err
	}
	payload := fmt.Sprintf("plan|%s|%d|%s", arm, gen, seal)
	sum := sha256.Sum256([]byte(payload))
	tok := hex.EncodeToString(sum[:])
	mark := filepath.Join(pth.PlansDir(), "issued."+tok[:16])
	if err := os.WriteFile(mark, []byte(fmt.Sprintf("%s %d\n", arm, gen)), 0o644); err != nil {
		return "", err
	}
	return tok, nil
}

// pinn_gate validates a commit token against the live session generation.
func pinn_gate(token, arm string, gen int) error {
	if token == "" || len(token) < 16 {
		return fmt.Errorf("empty plan token")
	}
	mark := filepath.Join(pth.PlansDir(), "issued."+token[:16])
	raw, err := os.ReadFile(mark)
	if err != nil {
		return fmt.Errorf("unknown plan token")
	}
	fields := strings.Fields(string(raw))
	if len(fields) < 2 {
		return fmt.Errorf("malformed plan token record")
	}
	if fields[0] != arm {
		return fmt.Errorf("plan token arm mismatch")
	}
	issued, err := strconv.Atoi(fields[1])
	if err != nil || issued != gen {
		return fmt.Errorf("plan token generation mismatch")
	}
	sess, err := zeb.Load()
	if err != nil {
		return err
	}
	if sess.ActiveGen != gen {
		return fmt.Errorf("stale plan token: issued at gen %d, session at %d", gen, sess.ActiveGen)
	}
	return nil
}
EOF

cat > "$env_root/idm/mark.go" <<'EOF'
package idm

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"

	"qxhub/pth"
)

// TxFor derives the deterministic transaction id for one commit identity.
func TxFor(arm string, gen int, seal string) string {
	payload := fmt.Sprintf("tx|%s|%d|%s", arm, gen, seal)
	sum := sha256.Sum256([]byte(payload))
	return hex.EncodeToString(sum[:])[:24]
}

// dur_mark records a transaction id after its commit lands.
func dur_mark(tx string) error {
	if err := pth.EnsureDirs(); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(pth.TxnsDir(), tx), []byte("1\n"), 0o644)
}

// dur_seen reports whether a transaction id has already committed.
func dur_seen(tx string) (bool, error) {
	if err := pth.EnsureDirs(); err != nil {
		return false, err
	}
	if _, err := os.Stat(filepath.Join(pth.TxnsDir(), tx)); err != nil {
		if os.IsNotExist(err) {
			return false, nil
		}
		return false, err
	}
	return true, nil
}
EOF

cat > "$env_root/gst/wane.go" <<'EOF'
package gst

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"

	"qxhub/pth"
)

// hulm_wane walks generations from the newest down, keeps the first one whose
// manifest bytes still agree with the detached seal, and reports it as current.
func hulm_wane() (int, string, error) {
	gens := ListGenerations()
	if len(gens) == 0 {
		return 0, "", nil
	}
	for i := len(gens) - 1; i >= 0; i-- {
		gen := gens[i]
		dir := filepath.Join(pth.GenerationsDir(), strconv.Itoa(gen))
		manifest, mErr := os.ReadFile(filepath.Join(dir, "manifest.json"))
		sealRaw, sErr := os.ReadFile(filepath.Join(dir, "MSEAL"))
		seal := trimEOL(string(sealRaw))
		if mErr == nil && sErr == nil && SealBytes(manifest) == seal {
			if err := SetCurrent(gen); err != nil {
				return 0, "", err
			}
			return gen, seal, nil
		}
		dest := filepath.Join(pth.QuarantineDir(), strconv.Itoa(gen))
		for n := 1; ; n++ {
			if _, err := os.Stat(dest); os.IsNotExist(err) {
				break
			}
			dest = filepath.Join(pth.QuarantineDir(), fmt.Sprintf("%d-%d", gen, n))
		}
		if err := os.Rename(dir, dest); err != nil {
			return 0, "", err
		}
	}
	return 0, "", nil
}

func trimEOL(s string) string {
	for len(s) > 0 && (s[len(s)-1] == '\n' || s[len(s)-1] == '\r' || s[len(s)-1] == ' ') {
		s = s[:len(s)-1]
	}
	return s
}
EOF

cat > "$env_root/eng/curt.go" <<'EOF'
package eng

import (
	"qxhub/fyn"
	"qxhub/pex"
	"qxhub/zeb"
)

// curt_fold emits the audit for an interrupted (cut-phase) arm after its
// journal entry has been recorded.
func curt_fold(outPath string, plan *Plan, sess zeb.Session) error {
	audit := Audit{
		Arm:              plan.Arm,
		RuleRows:         []fyn.LaneRow{},
		RouteCount:       0,
		GroupCount:       0,
		CellOutcomes:     []pex.CellOut{},
		GroupKeys:        []string{},
		HopRecords:       []pex.HopRec{},
		PaneDigest:       plan.Pane,
		TwinDigest:       plan.Twin,
		ExpectedRowCap:   plan.RowCap,
		ExpectedGroupCap: plan.GroupCap,
		SessionFloor:     sess.Floor,
		SessionGen:       sess.ActiveGen,
		Interrupt:        true,
		RunStamp:         runStamp(plan.Arm, plan.Pane, sess.Floor, sess.ActiveGen),
		Generation:       0,
		ManifestSeal:     "",
		LedgerHead:       "",
		PlanToken:        plan.Token,
		Status:           "interrupted",
	}
	if h, ok, err := ledHead(); err == nil && ok {
		audit.LedgerHead = h
	}
	return writeAudit(outPath, audit)
}
EOF

cat > "$env_root/eng/rgy.go" <<'EOF'
package eng

import (
	"fmt"

	"qxhub/gst"
	"qxhub/led"
	"qxhub/zeb"
)

// rgy_knit rebuilds the durable session registry and the current generation
// pointer from the committed ledger after a registry loss.
func rgy_knit() error {
	ents, err := led.ReplayAll()
	if err != nil {
		return err
	}
	if len(ents) == 0 {
		return fmt.Errorf("no ledger to replay")
	}
	last := ents[len(ents)-1]
	sess := zeb.Session{
		ActiveGen: last.Gen,
		Floor:     last.Floor,
		Epoch:     last.Epoch,
		Anchor:    zeb.SealAnchor(last.Gen, last.Floor, last.Epoch),
		LastArm:   last.Arm,
	}
	if err := zeb.Save(sess); err != nil {
		return err
	}
	return gst.SetCurrent(last.Gen)
}

// ReplayRegistry is the public wrapper around rgy_knit.
func ReplayRegistry() error {
	return rgy_knit()
}
EOF

bash "$env_root/scripts/build_all.sh"

for arm in dense sparse weave starve held_out side_cut side_rcv side_prt side_stl; do
  "$env_root/bin/lb_drive" --arm "$arm" --out "$out"
done

echo "oracle route recompose ok"
