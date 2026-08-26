#!/bin/bash
set -euo pipefail

cd /app/environment

cat > internal/stage/bind.go <<'EOF'
package stage

import (
	"fmt"

	"kvlab/internal/active"
	"kvlab/internal/hash"
	"kvlab/internal/meta"
	"kvlab/internal/session"
	"kvlab/internal/store"
	"kvlab/k3"
)

func priorAnchor(sess session.File, profile string) string {
	for i := len(sess.Runs) - 1; i >= 0; i-- {
		if sess.Runs[i].Profile == profile {
			return sess.Runs[i].StageTranscriptHex
		}
	}
	return ""
}

func BindMaterial(root string, v active.View, profile string) (bound []byte, content string, admit string, err error) {
	gen := v.TargetsGen()
	manifest, err := store.ManifestBytes(root, v.Prof.ImageTag)
	if err != nil {
		return nil, "", "", err
	}
	_, targetsRaw, err := meta.TargetsVersion(root, gen)
	if err != nil {
		return nil, "", "", err
	}
	raw := append(manifest, targetsRaw...)
	sess, _ := session.Load(root)
	if chain := priorAnchor(sess, profile); chain != "" {
		raw = append([]byte(chain), raw...)
	}
	hint := fmt.Sprintf("t%d", gen)
	seq := v.Expiry() - int64(v.StepIdx)
	bound, err = k3.BindM4(raw, seq, hint)
	if err != nil {
		return nil, "", "", err
	}
	content = hash.Hex(bound)
	admit = hash.OfBytes(bound, []byte(v.Admission()), []byte(fmt.Sprintf("%d", v.PullMode())))
	return bound, content, admit, nil
}
EOF

cat > internal/stage/mirror.go <<'EOF'
package stage

import (
	"encoding/json"
	"os"

	"kvlab/f2"
	"kvlab/internal/active"
	"kvlab/internal/ledger"
)

type MirrorState struct {
	MaxTier int    `json:"max_tier"`
	Epoch   int    `json:"epoch"`
	Owner   string `json:"owner"`
}

func replicaTier(root string, v active.View) int {
	tier := v.Step.MirrorTier
	if !v.Prof.ReplicaFlip {
		return tier
	}
	catRaw, err := os.ReadFile(root + "/fixtures/store/catalog.json")
	if err != nil {
		return tier
	}
	var cat struct {
		Replicas map[string]string `json:"replicas"`
	}
	if json.Unmarshal(catRaw, &cat) != nil {
		return tier
	}
	if alt, ok := cat.Replicas[v.Prof.ImageTag]; ok && alt != "" {
		return 1
	}
	return tier
}

func ReadMirrorState(root string) (MirrorState, error) {
	path := root + "/../state/mirror_view.json"
	raw, err := os.ReadFile(path)
	if err != nil {
		return MirrorState{}, err
	}
	var st MirrorState
	if err := json.Unmarshal(raw, &st); err != nil {
		return MirrorState{}, err
	}
	return st, nil
}

func WriteMirrorState(root string, st MirrorState) error {
	stateDir := root + "/../state"
	if err := os.MkdirAll(stateDir, 0o755); err != nil {
		return err
	}
	raw, err := json.Marshal(st)
	if err != nil {
		return err
	}
	if err := os.WriteFile(stateDir+"/mirror_view.json", raw, 0o644); err != nil {
		return err
	}
	return os.WriteFile(stateDir+"/mirror_view.owner", []byte(st.Owner), 0o644)
}

func RecoverMirror(root, profile string, v active.View) MirrorState {
	_ = root
	_ = profile
	_ = v
	return MirrorState{}
}

func ProbeMirror(root, profile string, v active.View) (ready bool, tier int, err error) {
	tier = replicaTier(root, v)
	prior, err := ReadMirrorState(root)
	if err != nil {
		prior = RecoverMirror(root, profile, v)
	}
	epoch := 0
	if prior.Owner == profile {
		epoch = prior.Epoch
	}
	st := MirrorState{
		MaxTier: tier,
		Epoch:   epoch + 1,
		Owner:   profile,
	}
	if err := ledger.Append(root, ledger.Event{
		Profile: profile,
		Step:    v.StepIdx,
		Tier:    st.MaxTier,
		Epoch:   st.Epoch,
		Owner:   st.Owner,
	}); err != nil {
		return false, tier, err
	}
	if err := WriteMirrorState(root, st); err != nil {
		return false, tier, err
	}
	need := 2
	ok, err := f2.ScopeV2(root, need)
	return ok, tier, err
}
EOF

cat > internal/stage/transcript.go <<'EOF'
package stage

import (
	"kvlab/internal/hash"
	"kvlab/internal/lane"
)

func AssembleTranscript(lf lane.File) string {
	ready := "false"
	if lf.Stage.SyncReady {
		ready = "true"
	}
	return hash.OfBytes(
		[]byte(lf.Stage.PullDigest),
		[]byte(ready),
		[]byte(lf.Stage.WalkDigest),
		[]byte(lf.Stage.AdmitDigest),
	)
}
EOF

cat > internal/lane/quorum.go <<'EOF'
package lane

import "fmt"

func ValidateQuorum(lf File) error {
	if lf.Stage.PullDigest == "" || lf.Stage.WalkDigest == "" || lf.Stage.AdmitDigest == "" {
		return fmt.Errorf("incomplete stage lane for %s", lf.Profile)
	}
	if lf.Stage.PullStepIdx != lf.Stage.SyncStepIdx || lf.Stage.PullStepIdx != lf.Stage.WalkStepIdx {
		return fmt.Errorf("step mismatch: pull=%d sync=%d walk=%d", lf.Stage.PullStepIdx, lf.Stage.SyncStepIdx, lf.Stage.WalkStepIdx)
	}
	return nil
}
EOF

cat > internal/export/rollup.go <<'EOF'
package export

import (
	"encoding/json"
	"io"
	"sort"

	"kvlab/internal/row"
)

func Rollup(rows []row.RunRow, sink io.Writer) error {
	profiles := []string{}
	seen := map[string]struct{}{}
	for _, r := range rows {
		if _, ok := seen[r.Profile]; ok {
			continue
		}
		seen[r.Profile] = struct{}{}
		profiles = append(profiles, r.Profile)
	}
	sort.Strings(profiles)
	doc := row.Export{
		Profiles:     profiles,
		Runs:         rows,
		ReportDigest: row.ReportDigest(rows),
	}
	enc := json.NewEncoder(sink)
	enc.SetEscapeHTML(false)
	enc.SetIndent("", "")
	return enc.Encode(doc)
}
EOF

cat > internal/seal/confirm.go <<'EOF'
package seal

import (
	"kvlab/internal/active"
	"kvlab/internal/meta"
)

func ConfirmWalkRole(root string, v active.View, walkVersion int) bool {
	ver, err := ExpectedRole(root, v)
	if err != nil {
		return false
	}
	return ver == walkVersion
}

func ExpectedRole(root string, v active.View) (int, error) {
	ver, _, err := meta.TargetsVersion(root, v.TargetsGen())
	return ver, err
}
EOF

cat > f2/scope_v2.go <<'EOF'
package f2

import (
	"encoding/json"
	"os"
)

type mirrorView struct {
	MaxTier int    `json:"max_tier"`
	Epoch   int    `json:"epoch"`
	Owner   string `json:"owner"`
}

func ScopeV2(root string, depth int) (bool, error) {
	path := root + "/../state/mirror_view.json"
	raw, err := os.ReadFile(path)
	if err != nil {
		return false, nil
	}
	var view mirrorView
	if err := json.Unmarshal(raw, &view); err != nil {
		return false, err
	}
	return view.MaxTier >= depth, nil
}
EOF

cat > k3/bind_m4.go <<'EOF'
package k3

import (
	"errors"
)

func BindM4(raw []byte, seq int64, hint string) ([]byte, error) {
	if len(raw) == 0 {
		return nil, errors.New("empty payload")
	}
	if hint == "" {
		return nil, errors.New("empty hint")
	}
	if seq < 1_000_000_000 {
		seq = 1_000_000_000
	}
	out := append([]byte(nil), []byte(hint)...)
	out = append(out, byte(seq&0xFF))
	out = append(out, raw...)
	return out, nil
}
EOF

cat > p4/meta_walk.go <<'EOF'
package p4

import (
	"fmt"

	"kvlab/internal/active"
	"kvlab/internal/hash"
	"kvlab/internal/lane"
	"kvlab/internal/meta"
	"kvlab/j8"
)

type WalkResult struct {
	RoleVersion int    `json:"role_version"`
	WalkDigest  string `json:"walk_digest"`
	RouteMode   int    `json:"route_mode"`
}

func RunWalk(root, profile string, stepIdx int) (WalkResult, error) {
	view, err := active.Resolve(root, profile, stepIdx)
	if err != nil {
		return WalkResult{}, err
	}
	gen := view.TargetsGen()
	ver, raw, err := meta.TargetsVersion(root, gen)
	if err != nil {
		return WalkResult{}, err
	}
	endpoint := "http://127.0.0.1:18080"
	mode := view.WalkTransport()
	if view.Prof.ProxyRequired == 1 {
		endpoint = "http://127.0.0.1:18081"
	}
	_, _ = j8.RouteH1(endpoint, mode)
	dig := hash.OfBytes(raw, []byte(fmt.Sprintf("%d", mode)))
	lf, _ := lane.Load(root, profile)
	lf.Profile = profile
	lf.Stage.WalkVersion = ver
	lf.Stage.WalkDigest = dig
	lf.Stage.WalkStepIdx = stepIdx
	_ = lane.Save(root, lf)
	return WalkResult{RoleVersion: ver, WalkDigest: dig, RouteMode: mode}, nil
}
EOF

python3 <<'PY'
from pathlib import Path

path = Path("s2/collect_stage.go")
text = path.read_text()
text = text.replace(
    "func laneReady(lf lane.File) bool {\n\treturn lf.Stage.PullDigest != \"\" && lf.Stage.WalkDigest != \"\"\n}",
    "func laneReady(lf lane.File) bool {\n\treturn lf.Stage.PullDigest != \"\" && lf.Stage.WalkDigest != \"\" && lf.Stage.AdmitDigest != \"\"\n}",
)
text = text.replace(
    "func collectExpiry(view active.View) int64 {\n\treturn view.Prof.Expiry\n}",
    "func collectExpiry(view active.View) int64 {\n\treturn view.Expiry()\n}",
)
path.write_text(text)

path = Path("m7/sync_probe.go")
text = path.read_text()
text = text.replace(
    "lf.Stage.SyncStepIdx = lf.Stage.PullStepIdx",
    "lf.Stage.SyncStepIdx = stepIdx",
)
path.write_text(text)

path = Path("cmd/meta_walk/main.go")
text = path.read_text()
text = text.replace(
    "lf.Stage.PullStepIdx = *step",
    "lf.Stage.WalkStepIdx = *step",
)
path.write_text(text)
PY

bash /app/ci/rebuild.sh

run_profile() {
  local profile="$1"
  local step="$2"
  /app/bin/pull_gate --profile "$profile" --step "$step"
  /app/bin/sync_probe --profile "$profile" --step "$step"
  /app/bin/meta_walk --profile "$profile" --step "$step"
  /app/bin/collect_stage --profile "$profile" --out /app/output/kv_export.json
}

rm -rf /app/state
mkdir -p /app/state /app/output
rm -f /app/output/kv_export.json

run_profile p1 0
run_profile p2 0
run_profile p2 1
run_profile p3 0
run_profile p3 1

python3 <<'PY'
import hashlib
import json
import sys
from pathlib import Path

out = Path("/app/output/kv_export.json")
doc = json.loads(out.read_text(encoding="utf-8"))
runs = doc.get("runs", [])
if len(runs) < 5:
    sys.exit("expected five session runs")

ordered = sorted(runs, key=lambda r: (r["profile"], r["run_index"]))
payload = [
    {
        "profile": r["profile"],
        "run_index": r["run_index"],
        "role_version": r["role_version"],
        "content_digest": r["content_digest"],
        "delegation_expiry": r["delegation_expiry"],
        "stage_transcript_hex": r["stage_transcript_hex"],
    }
    for r in ordered
]
body = json.dumps(payload, separators=(",", ":"))
dig = hashlib.sha256(body.encode()).hexdigest()
if dig != doc.get("report_digest"):
    sys.exit("report_digest mismatch")

role_versions = {(r["profile"], r["run_index"]): r["role_version"] for r in runs}
if role_versions.get(("p1", 0)) != 1:
    sys.exit("p1 role_version step override mismatch")
if role_versions.get(("p2", 0)) != 1 or role_versions.get(("p2", 1)) != 2:
    sys.exit("p2 role_version step override mismatch")
if role_versions.get(("p3", 0)) != 1 or role_versions.get(("p3", 1)) != 2:
    sys.exit("p3 role_version catchup mismatch")

profiles = sorted(doc.get("profiles", []))
if profiles != ["p1", "p2", "p3"]:
    sys.exit("profiles list incomplete")
PY
