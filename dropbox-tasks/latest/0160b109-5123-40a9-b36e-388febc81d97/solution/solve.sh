#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/verifier/bin:/app/bin:/go/bin:/usr/local/go/bin:${PATH:-/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}"

cat >/app/environment/q7m/mix_a7.go <<'EOF'
package q7m

// mix_a7 folds step and family tags into coeff bits for facets.
func mix_a7(stepIx int, familyIx uint32, prevFamily uint32) uint64 {
	base := (uint64(familyIx) << 32) | uint64(prevFamily)
	return base ^ (uint64(stepIx) * 0x9E3779B97F4A7C15)
}
EOF

cat >/app/environment/q7m/stamp_help.go <<'EOF'
package q7m

// StampHelp applies offline fold transforms for diagnostics.
func StampHelp(v uint64) uint64 {
	return v ^ 0xA5A5A5A5A5A5A5A5
}

// Fold applies the package fold path used by the conversion engine.
func Fold(stepIx int, familyIx uint32, prevFamily uint32) uint64 {
	return mix_a7(stepIx, familyIx, prevFamily)
}
EOF

cat >/app/environment/r2v/pack_b2.go <<'EOF'
package r2v

import "encoding/binary"

// pack_b2 merges incoming pack bytes into durable storage during bind steps.
func pack_b2(dst *PackState, src *PackState, stampB uint32) uint32 {
	if dst == nil || src == nil {
		return 0
	}
	var v uint64
	if len(src.Blob) >= 8 {
		v = binary.BigEndian.Uint64(src.Blob[:8])
	}
	v ^= uint64(stampB) * 0x100000001
	if len(dst.Blob) >= 8 {
		prev := binary.BigEndian.Uint64(dst.Blob[:8])
		if prev == v {
			if stampB > dst.Stamp {
				dst.Stamp = stampB
			}
			if src.Stamp > dst.Stamp {
				dst.Stamp = src.Stamp
			}
			return dst.Stamp
		}
	}
	var out [8]byte
	binary.BigEndian.PutUint64(out[:], v)
	dst.Blob = out[:]
	if stampB > dst.Stamp {
		dst.Stamp = stampB
	}
	if src.Stamp > dst.Stamp {
		dst.Stamp = src.Stamp
	}
	return dst.Stamp
}
EOF

cat >/app/environment/s9k/seq_c9.go <<'EOF'
package s9k

// seq_c9 orders side-effect callbacks during per-target combine steps under warm rebuild.
func seq_c9(gateFirst bool, side func(), gate func()) uint32 {
	if gateFirst {
		if gate != nil {
			gate()
		}
		if side != nil {
			side()
		}
	} else {
		if side != nil {
			side()
		}
		if gate != nil {
			gate()
		}
	}
	return 0
}
EOF

cat >/app/environment/t4w/rows_d4.go <<'EOF'
package t4w

import (
	"fmt"
)

// rows_d4 materializes report rows from row state, bundle, and witness.
func rows_d4(rows []RowRec, bundle *BundleRec, wit *WitRec) []EmittedRow {
	var out []EmittedRow
	for _, r := range rows {
		facet := fmt.Sprintf("%016x", r.Facet)
		lag := 0
		feat, dep, ord := 1, 1, 1
		label := "settled"
		if wit != nil {
			if exp, ok := wit.Expected[r.ID]; ok && exp != r.Facet {
				lag = 1
				feat = 0
				label = "drift"
			}
			if pack, ok := wit.PackHex[r.ID]; ok {
				got := fmt.Sprintf("%016x", r.Facet)
				if pack != got {
					lag = 1
					dep = 0
					label = "drift"
				}
			}
		}
		if bundle != nil {
			if c, ok := bundle.Coeffs[r.ID]; ok && c != r.Facet {
				lag = 1
				ord = 0
				label = "drift"
			}
		}
		out = append(out, EmittedRow{
			TgtID:     r.ID,
			FacetHex:  facet,
			Lag:       lag,
			FeatRC:    feat,
			DepRC:     dep,
			OrdRC:     ord,
			SyncLabel: label,
		})
	}
	return out
}
EOF

cat >/app/environment/engine/probe_view.go <<'EOF'
package engine

import (
	"fmt"
	"io"
)

type ProbeSnap struct {
	DurableMatch bool
	Rows         int
}

// EmitStatusView writes human-readable health probe lines for operator status.
func EmitStatusView(w io.Writer, snap ProbeSnap) error {
	label := "drift"
	if snap.DurableMatch && snap.Rows > 0 {
		label = "settled"
	}
	_, err := fmt.Fprintf(w, "sync_label=%s durable_match=%v rows=%d\n", label, snap.DurableMatch, snap.Rows)
	return err
}
EOF

cat >/app/environment/engine/ph_seed.go <<'EOF'
package engine

import "ucg.local/workspace/q7m"

func FoldCoeff(step int, family, prev uint32, salt uint64) uint64 {
	return q7m.Fold(step, family, prev) ^ salt
}
EOF

cat >/app/environment/engine/edge_fold.go <<'EOF'
package engine

import (
	"bufio"
	"os"
	"strconv"
	"strings"
)

// ConvEdge is one directed conversion link from the seed graph.
type ConvEdge struct {
	From   string
	To     string
	Weight int
}

// LoadConversionEdges reads [[edges]] rows from edge_seed.toml.
func LoadConversionEdges(path string) ([]ConvEdge, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	var out []ConvEdge
	var cur *ConvEdge
	flush := func() {
		if cur != nil && cur.From != "" && cur.To != "" {
			if cur.Weight == 0 {
				cur.Weight = 1
			}
			out = append(out, *cur)
		}
		cur = nil
	}
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "[[edges]]" {
			flush()
			cur = &ConvEdge{}
			continue
		}
		if cur == nil {
			continue
		}
		if strings.HasPrefix(line, "from = ") {
			cur.From = strings.Trim(strings.TrimPrefix(line, "from = "), "\"")
		}
		if strings.HasPrefix(line, "to = ") {
			cur.To = strings.Trim(strings.TrimPrefix(line, "to = "), "\"")
		}
		if strings.HasPrefix(line, "weight = ") {
			cur.Weight, _ = strconv.Atoi(strings.TrimSpace(strings.TrimPrefix(line, "weight = ")))
		}
	}
	flush()
	return out, sc.Err()
}

// ApplyConversionEdges folds source facets into destinations per edge_seed order.
func ApplyConversionEdges(facets map[string]uint64, edges []ConvEdge) {
	for _, e := range edges {
		src, okSrc := facets[e.From]
		dst, okDst := facets[e.To]
		if !okSrc || !okDst {
			continue
		}
		w := e.Weight
		if w == 0 {
			w = 1
		}
		facets[e.To] = dst ^ (src * uint64(w))
	}
}

// SyncEchoFacets copies each primary facet onto its _echo twin after edge folding.
func SyncEchoFacets(facets map[string]uint64) {
	for _, p := range []string{"a1", "b2", "g3"} {
		if v, ok := facets[p]; ok {
			facets[p+"_echo"] = v
		}
	}
}
EOF

python3 - <<'PY'
from pathlib import Path

# Surgical body swaps (avoid whole-file heredoc inflation on tiny deltas).
tag = Path("/app/environment/engine/arm_cache_tag.go")
text = tag.read_text()
old = '''func ShouldAcceptCache(cacheDir, arm string) bool {
	entries, err := os.ReadDir(cacheDir)
	if err != nil {
		return false
	}
	hasBin := false
	for _, ent := range entries {
		if strings.HasSuffix(ent.Name(), ".bin") {
			hasBin = true
			break
		}
	}
	return hasBin
}'''
new = '''func ShouldAcceptCache(cacheDir, arm string) bool {
	got, ok := ReadCacheArmTag(cacheDir)
	return ok && got == arm
}'''
if old not in text:
    raise SystemExit("arm_cache_tag: ShouldAcceptCache body missing")
tag.write_text(text.replace(old, new, 1))

jou = Path("/app/environment/engine/journal_v3.go")
text = jou.read_text()
old = '''func WarmNeedsMutation(tip JournalTip, arm, phase string) bool {
	_ = tip
	_ = arm
	_ = phase
	return false
}'''
new = '''func WarmNeedsMutation(tip JournalTip, arm, phase string) bool {
	return phase == "warm" && tip.Arm == arm && tip.Phase == "replay"
}'''
if old not in text:
    raise SystemExit("journal_v3: WarmNeedsMutation body missing")
text = text.replace(old, new, 1)
old_body = 'body := "arm = \\"" + tip.Arm + "\\"\\nphase = \\"" + tip.Phase + "\\"\\ndigest = \\"" + tip.Digest + "\\"\\n"'
new_body = 'body := "arm = \\"" + tip.Arm + "\\"\\nphase = \\"" + tip.Phase + "\\"\\ndigest = \\"" + tip.Digest + "\\"\\nbind = \\"" + tip.Bind + "\\"\\n"'
if old_body not in text:
    raise SystemExit("journal_v3: WriteJournalTip body missing")
text = text.replace(old_body, new_body, 1)
jou.write_text(text)

pol = Path("/app/environment/engine/cache_policy.go")
text = pol.read_text()
old = '''func PreferCachedFacets(phase string, accept bool, durable map[string]*r2v.PackState, need []string, tip JournalTip, arm string, digester func([]string) string) bool {
	if phase != "warm" {
		return false
	}
	prim := map[string]bool{"a1": true, "b2": true, "g3": true}
	var hexes []string
	for _, id := range need {
		p := durable[id]
		if p == nil || len(p.Blob) < 8 {
			return false
		}
		if prim[id] {
			hexes = append(hexes, sprintf016(binary.BigEndian.Uint64(p.Blob[:8])))
		}
	}
	_ = accept
	_ = tip
	_ = arm
	_ = digester
	sort.Strings(hexes)
	return len(hexes) == 3
}'''
new = '''func PreferCachedFacets(phase string, accept bool, durable map[string]*r2v.PackState, need []string, tip JournalTip, arm string, digester func([]string) string) bool {
	if phase != "warm" || !accept || tip.Arm != arm || tip.Digest == "" || tip.Bind == "" {
		return false
	}
	pairs, ok := CacheBindPairs(durable, need)
	if !ok {
		return false
	}
	prim := map[string]bool{"a1": true, "b2": true, "g3": true}
	var hexes []string
	for _, id := range need {
		if !prim[id] {
			continue
		}
		p := durable[id]
		hexes = append(hexes, sprintf016(binary.BigEndian.Uint64(p.Blob[:8])))
	}
	sort.Strings(hexes)
	if digester(hexes) != tip.Digest {
		return false
	}
	return digester(pairs) == tip.Bind
}'''
if old not in text:
    raise SystemExit("cache_policy: PreferCachedFacets body missing")
pol.write_text(text.replace(old, new, 1))
print("patched arm_cache_tag journal_v3 cache_policy")
PY

bash /app/environment/scripts/build_ucg.sh
rm -rf /app/output/conversion_ledger.json /app/output/cache /app/output/run_traces /app/output/journal
mkdir -p /app/output/cache /app/output/run_traces /app/output/journal
/app/bin/ucg_run --scenario unit-conversion-graph --arm arm0 --phase cold
