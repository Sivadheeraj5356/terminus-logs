#!/usr/bin/env bash
set -euo pipefail

cd /app
export PATH="/usr/local/go/bin:/app:${PATH}"
export GOCACHE="${GOCACHE:-/tmp/chronctl-go-cache}"
GO=/usr/local/go/bin/go
mkdir -p /app/output "$GOCACHE"
chmod 0777 /app/output || true

write_clock() {
  cat > clock/op_a.go <<'EOF'
package clock

const nanoPerSecond int64 = 1_000_000_000

func fuse_a(sec int64, nsec int64) int64 {
	return sec*nanoPerSecond + nsec
}

func shift_a(offsetMin int) int64 {
	return int64(offsetMin) * 60 * nanoPerSecond
}

func apply_a(wall int64, offsetMin int) int64 {
	return wall - shift_a(offsetMin)
}

func fold_a(wall int64) int64 {
	return wall / nanoPerSecond
}

func UtcNs(sec int64, nsec int64, offsetMin int) int64 {
	wall := fuse_a(sec, nsec)
	shifted := apply_a(wall, offsetMin)
	_ = fold_a(shifted)
	return shifted
}
EOF
}

write_ledger() {
  cat > ledger/op_b.go <<'EOF'
package ledger

func arm_a(left int, right int) int {
	if left > right {
		return right
	}
	return left
}

func arm_b(left int, right int) int {
	if left <= right {
		return left
	}
	return right
}

func pick_a(left int, right int) int {
	_ = arm_a(left, right)
	return arm_b(left, right)
}

func gap_a(left int, right int) int {
	if left > right {
		return left - right
	}
	return right - left
}

func LowVal(left int, right int) int {
	_ = gap_a(left, right)
	return pick_a(left, right)
}

func AbsN(leftCount int, rightCount int) int {
	_ = rightCount
	return leftCount
}

func LeanA(leftBase int, rightBase int) bool {
	return leftBase <= rightBase
}

func Plan(leftBase int, rightBase int, leftCount int, rightCount int) (int, bool) {
	merged := LowVal(leftBase, rightBase)
	span := AbsN(leftCount, rightCount)
	return merged + span, LeanA(leftBase, rightBase)
}
EOF
}

write_rank() {
  cat > rank/op_c.go <<'EOF'
package rank

import "fmt"

func f0_a(wall int64) string {
	return fmt.Sprintf("%020d", wall)
}

func f1_a(anchor int) string {
	return fmt.Sprintf("%06d", anchor)
}

func f2_a(segID int) string {
	return fmt.Sprintf("%06d", segID)
}

func f3_a(seq int) string {
	return fmt.Sprintf("%08d", seq)
}

func join_a(parts ...string) string {
	out := ""
	for i, part := range parts {
		if i > 0 {
			out += "-"
		}
		out += part
	}
	return out
}

func dims_a() (int, int, int, int) {
	return 20, 6, 6, 8
}

func KeyBlob(wall int64, anchor int, segID int, seq int) string {
	_, _, _, _ = dims_a()
	return join_a(f0_a(wall), f1_a(anchor), f2_a(segID), f3_a(seq))
}
EOF
}

write_digest() {
  cat > internal/digest/fingerprint.go <<'EOF'
package digest

import (
	"crypto/sha256"
	"encoding/hex"
	"strings"
)

func MixHex(actions []string) string {
	if len(actions) == 0 {
		return hex_a("")
	}
	return hex_a(strings.Join(actions, "|"))
}

func hex_a(raw string) string {
	sum := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(sum[:])
}
EOF
}

write_seal() {
  mkdir -p internal/seal
  cat > internal/seal/bind.go <<'EOF'
package seal

import (
	"crypto/sha256"
	"encoding/hex"
	"strconv"

	"chronctl/internal/digest"
)

func GlueX(epoch int, actions []string) string {
	mix := digest.MixHex(actions)
	sum := sha256.Sum256([]byte(strconv.Itoa(epoch) + ":" + mix))
	return hex.EncodeToString(sum[:])
}
EOF
}

write_cord() {
  mkdir -p internal/cord
  cat > internal/cord/rollup.go <<'EOF'
package cord

import (
	"crypto/sha256"
	"encoding/hex"
)

func KnitA(priorHex string, localSealHex string) string {
	sum := sha256.Sum256([]byte(priorHex + ":" + localSealHex))
	return hex.EncodeToString(sum[:])
}

func glue_a(left string, right string) string {
	sum := sha256.Sum256([]byte(left + "|" + right))
	return hex.EncodeToString(sum[:])
}

func KnitB(left string, right string) string {
	return glue_a(left, right)
}
EOF
}

write_policy() {
  mkdir -p internal/policy
  cat > internal/policy/rotate.go <<'EOF'
package policy

import (
	"encoding/json"
	"os"
)

type Threshold struct {
	AfterEvents int `json:"after_events"`
	EpochBump   int `json:"epoch_bump"`
}

type Schedule struct {
	Revision     string      `json:"revision"`
	GenesisPrior string      `json:"genesis_prior"`
	Thresholds   []Threshold `json:"thresholds"`
}

func ReadTab(path string) (*Schedule, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var sc Schedule
	if err := json.Unmarshal(raw, &sc); err != nil {
		return nil, err
	}
	return &sc, nil
}

func BumpFor(sc *Schedule, packEventsBefore int) int {
	if sc == nil {
		return 0
	}
	total := 0
	for _, th := range sc.Thresholds {
		if packEventsBefore >= th.AfterEvents {
			total += th.EpochBump
		}
	}
	return total
}

func SeedTok(sc *Schedule) string {
	if sc == nil || sc.GenesisPrior == "" {
		return "genesis"
	}
	return sc.GenesisPrior
}
EOF
}

write_probe() {
  cat > internal/harness/probe.go <<'EOF'
package harness

import (
	"fmt"

	"chronctl/internal/sim"
	"chronctl/pkg/api"
)

func SpotA(pack *api.Pack, name string) (*api.ScenarioResult, error) {
	sched := loadRotate()
	prior := "genesis"
	if sched != nil && sched.GenesisPrior != "" {
		prior = sched.GenesisPrior
	}
	cum := 0
	for i := range pack.Scenarios {
		row := sim.WorkA(&pack.Scenarios[i], prior, cum, sched)
		if pack.Scenarios[i].Name == name {
			return &row, nil
		}
		prior = row.TimelineHeadHex
		cum += row.EventsReplayed
	}
	return nil, fmt.Errorf("scenario not found: %s", name)
}
EOF
}

write_scenario() {
  python3 - <<'PY'
from pathlib import Path
path = Path("internal/sim/scenario.go")
text = path.read_text()
text = text.replace(
    "if replay[i].origSeq > replay[j].origSeq {",
    "if replay[i].seq > replay[j].seq {",
)
path.write_text(text)
PY
}

verify_clock_sources() {
  grep -q 'wall - shift_a' clock/op_a.go
  grep -q 'func UtcNs' clock/op_a.go
}

verify_ledger_sources() {
  grep -q 'func Plan' ledger/op_b.go
  grep -q 'return leftCount' ledger/op_b.go
  grep -q 'leftBase <= rightBase' ledger/op_b.go
}

verify_rank_sources() {
  grep -q 'f1_a(anchor), f2_a(segID), f3_a(seq)' rank/op_c.go
  grep -q 'func KeyBlob' rank/op_c.go
}

verify_digest_sources() {
  grep -q 'func MixHex' internal/digest/fingerprint.go
  ! grep -q 'sort.Strings' internal/digest/fingerprint.go
}

verify_seal_sources() {
  grep -q 'strconv.Itoa(epoch)' internal/seal/bind.go
  grep -q 'digest.MixHex' internal/seal/bind.go
}

verify_cord_sources() {
  grep -q 'priorHex + ":" + localSealHex' internal/cord/rollup.go
  grep -q 'func KnitA' internal/cord/rollup.go
}

verify_policy_sources() {
  grep -q 'total += th.EpochBump' internal/policy/rotate.go
  grep -q 'func BumpFor' internal/policy/rotate.go
}

verify_probe_sources() {
  grep -q 'cum += row.EventsReplayed' internal/harness/probe.go
  grep -q 'prior = row.TimelineHeadHex' internal/harness/probe.go
}

verify_scenario_sources() {
  grep -q 'local_seal' internal/sim/scenario.go
  grep -q 'replay\[i\].seq > replay\[j\].seq' internal/sim/scenario.go
  grep -q 'fold_head' internal/sim/scenario.go
  grep -q 'epoch_bump' internal/sim/scenario.go
}

verify_sources() {
  verify_clock_sources
  verify_ledger_sources
  verify_rank_sources
  verify_digest_sources
  verify_seal_sources
  verify_cord_sources
  verify_policy_sources
  verify_probe_sources
  verify_scenario_sources
}

verify_build() {
  "$GO" build -buildvcs=false -o /tmp/chronctl-verify ./cmd/chronctl
  test -x /tmp/chronctl-verify
  rm -f /tmp/chronctl-verify
}

write_clock
write_ledger
write_rank
write_digest
write_seal
write_cord
write_policy
write_probe
write_scenario
verify_sources
verify_build

"$GO" build -buildvcs=false -o /app/chronctl ./cmd/chronctl
chmod a+rx /app/chronctl || true
/app/chronctl -pack /app/data/scenarios.json -out /app/output/timeline_report.json
