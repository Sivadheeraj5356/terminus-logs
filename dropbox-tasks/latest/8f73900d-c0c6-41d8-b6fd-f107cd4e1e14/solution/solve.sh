#!/usr/bin/env bash
# Oracle solve — task identity partial-deploy-rollback-orchestrator token 2b850385
set -euo pipefail

APP=/app
PATH="/usr/local/go/bin:${PATH}"

python3 <<'PY'
from pathlib import Path

gate = Path("/app/vl/rbx_env_gate.sh")
text = gate.read_text()
needle = 'if [[ ! -f /app/data/deploy/release-state.json ]]; then'
insert = '''if [[ "${ROLLBACK_INCIDENT_ID}" != "$(python3 -c "import json; print(json.load(open('/app/state/deploy-status.json'))['incident_id'])")" ]]; then
  echo "invalid incident id" >&2
  exit 1
fi

'''
if "invalid incident id" not in text:
    text = text.replace(needle, insert + needle)
    gate.write_text(text)

core = Path("/app/vl/rbx_apply_core.sh")
ctext = core.read_text()
changed = False
digest_old = (
    'lines = sorted(f"{svc}|{row[\'status\']}" for svc, row in status["services"].items())\n'
    'digest = hashlib.sha256("\\n".join(lines).encode()).hexdigest()'
)
digest_new = (
    'order = json.load(open("/app/data/deploy/forward-order.json"))\n'
    'lines = [f"{svc}|{status[\'services\'][svc][\'status\']}" for svc in order if svc in status["services"]]\n'
    'digest = hashlib.sha256("\\n".join(lines).encode()).hexdigest()'
)
if digest_old in ctext:
    ctext = ctext.replace(digest_old, digest_new)
    changed = True
if "truth ledger capture_sequence stale" not in ctext:
    ctext = ctext.replace(
        '    sys.exit(6)\nPY',
        '''    sys.exit(6)
ledger = json.load(open("/app/state/truth-ledger.json"))
if ledger.get("capture_sequence") != manifest.get("capture_sequence"):
    print("truth ledger capture_sequence stale", file=sys.stderr)
    sys.exit(7)
PY''',
    )
    changed = True
if "wave midpipe snapshot stale" not in ctext:
    wave_block = (
        "python3 <<'SNAP'\n"
        "import json, sys\n"
        "snapshot = json.load(open('/app/state/wave-midpipe-snapshot.json'))\n"
        "manifest = json.load(open('/app/state/inspect-manifest.json'))\n"
        "plan = json.load(open('/app/output/rollback-plan.json'))\n"
        "if snapshot.get('capture_sequence') != manifest.get('capture_sequence'):\n"
        "    print('wave midpipe snapshot stale', file=sys.stderr)\n"
        "    sys.exit(8)\n"
        "if snapshot.get('plan_hash') != plan.get('hash'):\n"
        "    print('wave midpipe snapshot plan_hash stale', file=sys.stderr)\n"
        "    sys.exit(9)\n"
        "if snapshot.get('manifest_release_digest') != manifest.get('release_digest'):\n"
        "    print('wave midpipe snapshot release_digest stale', file=sys.stderr)\n"
        "    sys.exit(10)\n"
        "SNAP\n\n"
        "mkdir -p /app/state\n"
    )
    ctext = ctext.replace("mkdir -p /app/state\n", wave_block)
    changed = True
if changed:
    core.write_text(ctext)

egress_lane_block = '''python3 <<'LANE'
import hashlib, json, sys
lane_path = "/app/state/egress-lane-midpipe.json"
try:
    lane = json.load(open(lane_path))
except FileNotFoundError:
    print("missing egress lane midpipe", file=sys.stderr)
    sys.exit(11)
manifest = json.load(open("/app/state/inspect-manifest.json"))
plan = json.load(open("/app/output/rollback-plan.json"))
if lane.get("capture_sequence") != manifest.get("capture_sequence"):
    print("egress lane capture_sequence stale", file=sys.stderr)
    sys.exit(12)
if lane.get("plan_hash") != plan.get("hash"):
    print("egress lane plan_hash stale", file=sys.stderr)
    sys.exit(13)
lines = [f"wave|{idx}|{step}" for idx, step in enumerate(plan["steps"])]
digest = hashlib.sha256("\\n".join(lines).encode()).hexdigest()
if lane.get("wave_step_sequence_digest") != digest:
    print("egress lane wave_step_sequence_digest stale", file=sys.stderr)
    sys.exit(14)
snapshot = json.load(open("/app/state/wave-midpipe-snapshot.json"))
chain_lines = [
    f"capture|{lane.get('capture_sequence')}",
    f"plan|{lane.get('plan_hash')}",
    f"release|{snapshot.get('manifest_release_digest')}",
    f"wave|{lane.get('wave_step_sequence_digest')}",
]
chain_digest = hashlib.sha256("\\n".join(chain_lines).encode()).hexdigest()
if lane.get("midpipe_chain_digest") != chain_digest:
    print("egress lane midpipe_chain_digest stale", file=sys.stderr)
    sys.exit(16)
LANE

python3 <<'REPLAY'
import json, sys
ledger_path = "/app/state/rollback-run-ledger.json"
manifest = json.load(open("/app/state/inspect-manifest.json"))
plan = json.load(open("/app/output/rollback-plan.json"))
try:
    ledger = json.load(open(ledger_path))
except FileNotFoundError:
    ledger = None
if ledger and ledger.get("last_plan_hash") == plan.get("hash") and ledger.get("last_capture_sequence") == manifest.get("capture_sequence"):
    print("rollback replay blocked", file=sys.stderr)
    sys.exit(15)
REPLAY

'''

witness_block = '''python3 <<'WITNESS'
import hashlib, json, sys
witness_path = "/app/state/rollback-witness-bundle.json"
try:
    witness = json.load(open(witness_path))
except FileNotFoundError:
    print("missing witness bundle", file=sys.stderr)
    sys.exit(17)
lane = json.load(open("/app/state/egress-lane-midpipe.json"))
manifest = json.load(open("/app/state/inspect-manifest.json"))
plan = json.load(open("/app/output/rollback-plan.json"))
status = json.load(open("/app/state/deploy-status.json"))
if witness.get("midpipe_chain_digest") != lane.get("midpipe_chain_digest"):
    print("witness midpipe_chain_digest stale", file=sys.stderr)
    sys.exit(18)
if witness.get("capture_sequence") != manifest.get("capture_sequence"):
    print("witness capture_sequence stale", file=sys.stderr)
    sys.exit(19)
if witness.get("plan_hash") != plan.get("hash"):
    print("witness plan_hash stale", file=sys.stderr)
    sys.exit(20)
lines = [
    f"incident|{status.get('incident_id')}",
    "zone|primary",
    f"chain|{lane.get('midpipe_chain_digest')}",
    f"capture|{manifest.get('capture_sequence')}",
    f"plan|{plan.get('hash')}",
]
token = hashlib.sha256("\\n".join(lines).encode()).hexdigest()
if witness.get("zone_quorum_token") != token:
    print("witness zone_quorum_token stale", file=sys.stderr)
    sys.exit(21)
WITNESS

'''
topology_block = '''python3 <<'TOPO'
import hashlib, json, sys
latch_path = "/app/state/topology-epoch-latch.json"
try:
    latch = json.load(open(latch_path))
except FileNotFoundError:
    print("missing topology epoch latch", file=sys.stderr)
    sys.exit(22)
manifest = json.load(open("/app/state/inspect-manifest.json"))
plan = json.load(open("/app/output/rollback-plan.json"))
graph = json.load(open("/app/data/topology/rollback-graph.json"))
if latch.get("capture_sequence") != manifest.get("capture_sequence"):
    print("topology latch capture_sequence stale", file=sys.stderr)
    sys.exit(23)
if latch.get("plan_hash") != plan.get("hash"):
    print("topology latch plan_hash stale", file=sys.stderr)
    sys.exit(24)
lines = []
for svc in sorted(graph):
    for dep in sorted(graph.get(svc) or []):
        lines.append(f"dep|{svc}|{dep}")
graph_epoch = hashlib.sha256("\\n".join(lines).encode()).hexdigest()
if latch.get("graph_epoch_digest") != graph_epoch:
    print("topology latch graph_epoch_digest stale", file=sys.stderr)
    sys.exit(25)
expect = hashlib.sha256(
    f"topo-latch|{latch.get('capture_sequence')}|{latch.get('plan_hash')}|{graph_epoch}".encode()
).hexdigest()
if latch.get("latch_digest") != expect:
    print("topology latch_digest stale", file=sys.stderr)
    sys.exit(26)
TOPO

'''
run_ledger_write = '''python3 <<'LEDGER'
import json, os
ledger_path = "/app/state/rollback-run-ledger.json"
manifest = json.load(open("/app/state/inspect-manifest.json"))
plan = json.load(open("/app/output/rollback-plan.json"))
epoch = 1
if os.path.isfile(ledger_path):
    prev = json.load(open(ledger_path))
    if prev.get("last_plan_hash") == plan.get("hash") and prev.get("last_capture_sequence") == manifest.get("capture_sequence"):
        epoch = prev.get("apply_epoch", 0) + 1
    else:
        epoch = 1
payload = {
    "apply_epoch": epoch,
    "last_plan_hash": plan.get("hash"),
    "last_capture_sequence": manifest.get("capture_sequence"),
}
json.dump(payload, open(ledger_path, "w"), indent=2)
LEDGER

'''
core = Path("/app/vl/rbx_apply_core.sh")
ctext = core.read_text()
if "missing egress lane midpipe" not in ctext:
    ctext = ctext.replace("mkdir -p /app/state\n", egress_lane_block + run_ledger_write + witness_block + topology_block + "mkdir -p /app/state\n")
    core.write_text(ctext)
if "missing topology epoch latch" not in ctext:
    ctext = core.read_text()
    if "missing topology epoch latch" not in ctext:
        ctext = ctext.replace("mkdir -p /app/state\n", topology_block + "mkdir -p /app/state\n")
        core.write_text(ctext)
PY

cat > "$APP/internal/rbx_a1/rbx_a1st.go" <<'CAPTURE'
package rbxa1

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"strings"
)

type ServiceStatus struct {
	Status   string `json:"status"`
	Version  string `json:"version"`
	Previous string `json:"previous"`
	Target   string `json:"target,omitempty"`
}

type DeployStatus struct {
	Release  string                   `json:"release"`
	Incident string                   `json:"incident_id"`
	Services map[string]ServiceStatus `json:"services"`
}

type TruthBindings struct {
	TruthSource     string `json:"truth_source"`
	ReleaseDigest   string `json:"release_digest"`
	ForwardDigest   string `json:"forward_digest"`
	RegistryRelease string `json:"registry_release"`
	CaptureSequence int    `json:"capture_sequence"`
}

func releaseDigest(status DeployStatus) (string, error) {
	raw, err := os.ReadFile("/app/data/deploy/forward-order.json")
	if err != nil {
		return "", err
	}
	var order []string
	if err := json.Unmarshal(raw, &order); err != nil {
		return "", err
	}
	lines := make([]string, 0, len(order))
	for _, svc := range order {
		row, ok := status.Services[svc]
		if !ok {
			continue
		}
		lines = append(lines, svc+"|"+row.Status)
	}
	sum := sha256.Sum256([]byte(strings.Join(lines, "\n")))
	return hex.EncodeToString(sum[:]), nil
}

func forwardDigest() (string, error) {
	raw, err := os.ReadFile("/app/data/deploy/forward-order.json")
	if err != nil {
		return "", err
	}
	var order []string
	if err := json.Unmarshal(raw, &order); err != nil {
		return "", err
	}
	sum := sha256.Sum256([]byte(strings.Join(order, "\n")))
	return hex.EncodeToString(sum[:]), nil
}

func registryRelease(incidentID string) (string, error) {
	raw, err := os.ReadFile("/app/data/incident/registry.json")
	if err != nil {
		return "", err
	}
	var reg map[string]struct {
		Release string `json:"release"`
	}
	if err := json.Unmarshal(raw, &reg); err != nil {
		return "", err
	}
	row, ok := reg[incidentID]
	if !ok {
		return "", os.ErrNotExist
	}
	return row.Release, nil
}

func writeTruthLedger(incidentID string) (int, error) {
	seq := 1
	path := "/app/state/truth-ledger.json"
	if raw, err := os.ReadFile(path); err == nil {
		var prev struct {
			CaptureSequence int `json:"capture_sequence"`
		}
		if json.Unmarshal(raw, &prev) == nil && prev.CaptureSequence > 0 {
			seq = prev.CaptureSequence + 1
		}
	}
	ledger := map[string]interface{}{
		"capture_sequence": seq,
		"incident_id":      incidentID,
	}
	out, err := json.MarshalIndent(ledger, "", "  ")
	if err != nil {
		return 0, err
	}
	if err := os.WriteFile(path, out, 0o644); err != nil {
		return 0, err
	}
	return seq, nil
}

func CaptureTruth() error {
	raw, err := os.ReadFile("/app/data/deploy/release-state.json")
	if err != nil {
		return err
	}
	var status DeployStatus
	if err := json.Unmarshal(raw, &status); err != nil {
		return err
	}
	if err := os.MkdirAll("/app/state", 0o755); err != nil {
		return err
	}
	out, err := json.MarshalIndent(status, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile("/app/state/deploy-status.json", out, 0o644); err != nil {
		return err
	}
	seq, err := writeTruthLedger(status.Incident)
	if err != nil {
		return err
	}
	fwd, err := forwardDigest()
	if err != nil {
		return err
	}
	regRel, err := registryRelease(status.Incident)
	if err != nil {
		return err
	}
	relDigest, err := releaseDigest(status)
	if err != nil {
		return err
	}
	manifest := TruthBindings{
		TruthSource:     "release-state",
		ReleaseDigest:   relDigest,
		ForwardDigest:   fwd,
		RegistryRelease: regRel,
		CaptureSequence: seq,
	}
	mOut, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile("/app/state/inspect-manifest.json", mOut, 0o644)
}
CAPTURE

cat > "$APP/internal/rbx_c3/rbx_c3gr.go" <<'DEPS'
package rbxc3

import (
	"encoding/json"
	"fmt"
	"os"
)

func Load(path string) (map[string][]string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var g map[string][]string
	if err := json.Unmarshal(raw, &g); err != nil {
		return nil, err
	}
	return g, nil
}

func HasCycle(g map[string][]string) bool {
	visited := map[string]int{}
	var dfs func(string) bool
	dfs = func(node string) bool {
		if visited[node] == 1 {
			return true
		}
		if visited[node] == 2 {
			return false
		}
		visited[node] = 1
		for _, dep := range g[node] {
			if dfs(dep) {
				return true
			}
		}
		visited[node] = 2
		return false
	}
	for node := range g {
		if dfs(node) {
			return true
		}
	}
	return false
}

func RollbackOrder(g map[string][]string, updated []string) ([]string, error) {
	upd := map[string]bool{}
	for _, s := range updated {
		upd[s] = true
	}
	raw, err := os.ReadFile("/app/data/deploy/forward-order.json")
	if err != nil {
		return nil, err
	}
	var forward []string
	if err := json.Unmarshal(raw, &forward); err != nil {
		return nil, err
	}
	var filtered []string
	for _, svc := range forward {
		if upd[svc] {
			filtered = append(filtered, svc)
		}
	}
	order := make([]string, len(filtered))
	for i, svc := range filtered {
		order[len(filtered)-1-i] = svc
	}
	if !ValidRollbackOrder(order, g) {
		return nil, fmt.Errorf("invalid rollback order")
	}
	return order, nil
}

func ValidRollbackOrder(order []string, g map[string][]string) bool {
	pos := map[string]int{}
	set := map[string]bool{}
	for i, s := range order {
		pos[s] = i
		set[s] = true
	}
	for _, svc := range order {
		for _, dep := range g[svc] {
			if !set[dep] {
				continue
			}
			if pos[dep] < pos[svc] {
				return false
			}
		}
	}
	return true
}

func ValidateNoCycle(path string) error {
	g, err := Load(path)
	if err != nil {
		return err
	}
	if HasCycle(g) {
		return fmt.Errorf("cycle detected")
	}
	return nil
}
DEPS

cat > "$APP/internal/rbx_g7/rbx_g7el.go" <<'G7'
package rbxg7

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

func WaveSequenceDigest(steps []string) string {
	var lines []string
	for idx, step := range steps {
		lines = append(lines, fmt.Sprintf("wave|%d|%s", idx, step))
	}
	sum := sha256.Sum256([]byte(strings.Join(lines, "\n")))
	return hex.EncodeToString(sum[:])
}

func MidpipeChainDigest(captureSeq int, planHash, releaseDigest, waveDigest string) string {
	lines := []string{
		fmt.Sprintf("capture|%d", captureSeq),
		fmt.Sprintf("plan|%s", planHash),
		fmt.Sprintf("release|%s", releaseDigest),
		fmt.Sprintf("wave|%s", waveDigest),
	}
	sum := sha256.Sum256([]byte(strings.Join(lines, "\n")))
	return hex.EncodeToString(sum[:])
}

func WriteEgressLanemidpipe(planHash, releaseDigest string, steps []string, captureSeq int) error {
	waveDigest := WaveSequenceDigest(steps)
	payload := map[string]interface{}{
		"capture_sequence":          captureSeq,
		"plan_hash":                 planHash,
		"wave_step_sequence_digest": waveDigest,
		"midpipe_chain_digest":      MidpipeChainDigest(captureSeq, planHash, releaseDigest, waveDigest),
	}
	raw, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile("/app/state/egress-lane-midpipe.json", raw, 0o644)
}
G7

cat > "$APP/internal/rbx_i9/rbx_i9te.go" <<'I9'
package rbxi9

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
)

func GraphEpochDigest(path string) (string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	var g map[string][]string
	if err := json.Unmarshal(raw, &g); err != nil {
		return "", err
	}
	svcs := make([]string, 0, len(g))
	for svc := range g {
		svcs = append(svcs, svc)
	}
	sort.Strings(svcs)
	var lines []string
	for _, svc := range svcs {
		deps := append([]string{}, g[svc]...)
		sort.Strings(deps)
		for _, dep := range deps {
			lines = append(lines, fmt.Sprintf("dep|%s|%s", svc, dep))
		}
	}
	sum := sha256.Sum256([]byte(strings.Join(lines, "\n")))
	return hex.EncodeToString(sum[:]), nil
}

func LatchDigest(captureSeq int, planHash, graphEpoch string) string {
	sum := sha256.Sum256([]byte(fmt.Sprintf("topo-latch|%d|%s|%s", captureSeq, planHash, graphEpoch)))
	return hex.EncodeToString(sum[:])
}

func WriteTopologyEpochLatch(planHash string, captureSeq int) error {
	graphEpoch, err := GraphEpochDigest("/app/data/topology/rollback-graph.json")
	if err != nil {
		return err
	}
	payload := map[string]interface{}{
		"schema":             "rollback.topology-epoch.v1",
		"capture_sequence":   captureSeq,
		"plan_hash":          planHash,
		"graph_epoch_digest": graphEpoch,
		"latch_digest":       LatchDigest(captureSeq, planHash, graphEpoch),
	}
	raw, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile("/app/state/topology-epoch-latch.json", raw, 0o644)
}

func VerifyTopologyEpochLatch() error {
	raw, err := os.ReadFile("/app/state/topology-epoch-latch.json")
	if err != nil {
		return err
	}
	var latch struct {
		CaptureSequence  int    `json:"capture_sequence"`
		PlanHash         string `json:"plan_hash"`
		GraphEpochDigest string `json:"graph_epoch_digest"`
		LatchDigest      string `json:"latch_digest"`
	}
	if err := json.Unmarshal(raw, &latch); err != nil {
		return err
	}
	manifestRaw, err := os.ReadFile("/app/state/inspect-manifest.json")
	if err != nil {
		return err
	}
	var manifest struct {
		CaptureSequence int `json:"capture_sequence"`
	}
	if err := json.Unmarshal(manifestRaw, &manifest); err != nil {
		return err
	}
	planRaw, err := os.ReadFile("/app/output/rollback-plan.json")
	if err != nil {
		return err
	}
	var plan struct {
		Hash string `json:"hash"`
	}
	if err := json.Unmarshal(planRaw, &plan); err != nil {
		return err
	}
	if latch.CaptureSequence != manifest.CaptureSequence {
		return fmt.Errorf("topology latch capture_sequence mismatch")
	}
	if latch.PlanHash != plan.Hash {
		return fmt.Errorf("topology latch plan_hash mismatch")
	}
	graphEpoch, err := GraphEpochDigest("/app/data/topology/rollback-graph.json")
	if err != nil {
		return err
	}
	if latch.GraphEpochDigest != graphEpoch {
		return fmt.Errorf("topology latch graph_epoch_digest mismatch")
	}
	if latch.LatchDigest != LatchDigest(latch.CaptureSequence, latch.PlanHash, graphEpoch) {
		return fmt.Errorf("topology latch_digest mismatch")
	}
	return nil
}
I9

cat > "$APP/internal/rbx_h8/rbx_h8wq.go" <<'H8'
package rbxh8

// WriteWitnessBundle writes /app/state/rollback-witness-bundle.json.

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

func quorumToken(incidentID, zone, chainDigest string, captureSeq int, planHash string) string {
	lines := []string{
		fmt.Sprintf("incident|%s", incidentID),
		fmt.Sprintf("zone|%s", zone),
		fmt.Sprintf("chain|%s", chainDigest),
		fmt.Sprintf("capture|%d", captureSeq),
		fmt.Sprintf("plan|%s", planHash),
	}
	sum := sha256.Sum256([]byte(strings.Join(lines, "\n")))
	return hex.EncodeToString(sum[:])
}

func WriteWitnessBundle() error {
	laneRaw, err := os.ReadFile("/app/state/egress-lane-midpipe.json")
	if err != nil {
		return err
	}
	var lane struct {
		MidpipeChainDigest string `json:"midpipe_chain_digest"`
	}
	if err := json.Unmarshal(laneRaw, &lane); err != nil {
		return err
	}
	manifestRaw, err := os.ReadFile("/app/state/inspect-manifest.json")
	if err != nil {
		return err
	}
	var manifest struct {
		CaptureSequence int `json:"capture_sequence"`
	}
	if err := json.Unmarshal(manifestRaw, &manifest); err != nil {
		return err
	}
	planRaw, err := os.ReadFile("/app/output/rollback-plan.json")
	if err != nil {
		return err
	}
	var plan struct {
		Hash string `json:"hash"`
	}
	if err := json.Unmarshal(planRaw, &plan); err != nil {
		return err
	}
	statusRaw, err := os.ReadFile("/app/state/deploy-status.json")
	if err != nil {
		return err
	}
	var status struct {
		IncidentID string `json:"incident_id"`
	}
	if err := json.Unmarshal(statusRaw, &status); err != nil {
		return err
	}
	token := quorumToken(status.IncidentID, "primary", lane.MidpipeChainDigest, manifest.CaptureSequence, plan.Hash)
	bundle := map[string]interface{}{
		"capture_sequence":       manifest.CaptureSequence,
		"plan_hash":              plan.Hash,
		"midpipe_chain_digest":   lane.MidpipeChainDigest,
		"zone_quorum_token":      token,
	}
	out, err := json.MarshalIndent(bundle, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile("/app/state/rollback-witness-bundle.json", out, 0o644)
}
H8

cat > "$APP/internal/rbx_d4/rbx_d4wv.go" <<'SEQUENCE'
package rbxd4

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"rollbackctl/internal/rbx_b2"
	"rollbackctl/internal/rbx_c3"
	"rollbackctl/internal/rbx_g7"
	"rollbackctl/internal/rbx_i9"
)

type RollbackPlan struct {
	Steps   []string `json:"steps"`
	Release string   `json:"release"`
	Hash    string   `json:"hash"`
}

func VerifyManifestDigestBindings() error {
	raw, err := os.ReadFile("/app/state/inspect-manifest.json")
	if err != nil {
		return err
	}
	var manifest struct {
		TruthSource     string `json:"truth_source"`
		ReleaseDigest   string `json:"release_digest"`
		ForwardDigest   string `json:"forward_digest"`
		RegistryRelease string `json:"registry_release"`
	}
	if err := json.Unmarshal(raw, &manifest); err != nil {
		return err
	}
	if manifest.TruthSource != "release-state" {
		return fmt.Errorf("inspect manifest truth_source invalid")
	}
	statusRaw, err := os.ReadFile("/app/state/deploy-status.json")
	if err != nil {
		return err
	}
	var status struct {
		IncidentID string `json:"incident_id"`
		Services map[string]struct {
			Status string `json:"status"`
		} `json:"services"`
	}
	if err := json.Unmarshal(statusRaw, &status); err != nil {
		return err
	}
	fwdRaw, err := os.ReadFile("/app/data/deploy/forward-order.json")
	if err != nil {
		return err
	}
	var order []string
	if err := json.Unmarshal(fwdRaw, &order); err != nil {
		return err
	}
	lines := make([]string, 0, len(order))
	for _, svc := range order {
		row, ok := status.Services[svc]
		if !ok {
			continue
		}
		lines = append(lines, svc+"|"+row.Status)
	}
	sum := sha256.Sum256([]byte(strings.Join(lines, "\n")))
	digest := hex.EncodeToString(sum[:])
	if manifest.ReleaseDigest != digest {
		return fmt.Errorf("inspect manifest digest mismatch")
	}
	fwdSum := sha256.Sum256([]byte(strings.Join(order, "\n")))
	fwdDigest := hex.EncodeToString(fwdSum[:])
	if manifest.ForwardDigest != fwdDigest {
		return fmt.Errorf("inspect manifest forward_digest mismatch")
	}
	regRaw, err := os.ReadFile("/app/data/incident/registry.json")
	if err != nil {
		return err
	}
	var reg map[string]struct {
		Release string `json:"release"`
	}
	if err := json.Unmarshal(regRaw, &reg); err != nil {
		return err
	}
	row, ok := reg[status.IncidentID]
	if !ok {
		return fmt.Errorf("incident not in registry")
	}
	if manifest.RegistryRelease != row.Release {
		return fmt.Errorf("inspect manifest registry_release mismatch")
	}
	return nil
}

func requireTruthBindings() error {
	raw, err := os.ReadFile("/app/state/inspect-manifest.json")
	if err != nil {
		return err
	}
	var manifest struct {
		CaptureSequence int `json:"capture_sequence"`
	}
	if err := json.Unmarshal(raw, &manifest); err != nil {
		return err
	}
	if err := VerifyManifestDigestBindings(); err != nil {
		return err
	}
	ledgerRaw, err := os.ReadFile("/app/state/truth-ledger.json")
	if err != nil {
		return err
	}
	var ledger struct {
		CaptureSequence int `json:"capture_sequence"`
	}
	if err := json.Unmarshal(ledgerRaw, &ledger); err != nil {
		return err
	}
	if manifest.CaptureSequence != ledger.CaptureSequence {
		return fmt.Errorf("truth ledger capture_sequence mismatch")
	}
	return nil
}

func writePlanSeal(planHash string) error {
	seal := map[string]string{
		"plan_hash": planHash,
		"seal":      "rollback-bound",
	}
	raw, err := json.MarshalIndent(seal, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile("/app/state/plan-seal.json", raw, 0o644)
}

func writeWavemidpipeSnapshot(planHash, releaseDigest string, captureSeq int) error {
	snap := map[string]interface{}{
		"capture_sequence":          captureSeq,
		"plan_hash":                 planHash,
		"manifest_release_digest":   releaseDigest,
	}
	raw, err := json.MarshalIndent(snap, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile("/app/state/wave-midpipe-snapshot.json", raw, 0o644)
}

func Build() error {
	if err := requireTruthBindings(); err != nil {
		return err
	}
	manifestRaw, err := os.ReadFile("/app/state/inspect-manifest.json")
	if err != nil {
		return err
	}
	var manifest struct {
		ReleaseDigest   string `json:"release_digest"`
		CaptureSequence int    `json:"capture_sequence"`
	}
	if err := json.Unmarshal(manifestRaw, &manifest); err != nil {
		return err
	}
	statusRaw, err := os.ReadFile("/app/state/deploy-status.json")
	if err != nil {
		return err
	}
	var status struct {
		Release  string `json:"release"`
		Services map[string]struct {
			Status string `json:"status"`
		} `json:"services"`
	}
	if err := json.Unmarshal(statusRaw, &status); err != nil {
		return err
	}
	var updated []string
	for svc, row := range status.Services {
		if row.Status == "updated" {
			updated = append(updated, svc)
		}
	}
	g, err := rbxc3.Load("/app/data/topology/rollback-graph.json")
	if err != nil {
		return err
	}
	steps, err := rbxc3.RollbackOrder(g, updated)
	if err != nil {
		return err
	}
	plan := RollbackPlan{Steps: steps, Release: status.Release}
	plan.Hash = rbxb2.WaveHash(steps, status.Release)
	if err := os.MkdirAll("/app/output", 0o755); err != nil {
		return err
	}
	out, err := json.MarshalIndent(plan, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile("/app/output/rollback-plan.json", out, 0o644); err != nil {
		return err
	}
	if err := writePlanSeal(plan.Hash); err != nil {
		return err
	}
	if err := writeWavemidpipeSnapshot(plan.Hash, manifest.ReleaseDigest, manifest.CaptureSequence); err != nil {
		return err
	}
	if err := rbxg7.WriteEgressLanemidpipe(plan.Hash, manifest.ReleaseDigest, plan.Steps, manifest.CaptureSequence); err != nil {
		return err
	}
	return rbxi9.WriteTopologyEpochLatch(plan.Hash, manifest.CaptureSequence)
}

func Emit(outPath string) error {
	if err := Build(); err != nil {
		return err
	}
	if outPath == "/app/output/rollback-plan.json" {
		return nil
	}
	raw, err := os.ReadFile("/app/output/rollback-plan.json")
	if err != nil {
		return err
	}
	return os.WriteFile(outPath, raw, 0o644)
}
SEQUENCE

cat > "$APP/internal/rbx_e5/rbx_e5ln.go" <<'SHIM'
package rbxe5

func LaneShim(steps []string) []string {
	return steps
}
SHIM

cat > "$APP/internal/rbx_b2/rbx_b2hx.go" <<'DIGEST'
package rbxb2

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
	"strings"
)

func WaveHash(steps []string, release string) string {
	var lines []string
	lines = append(lines, fmt.Sprintf("release|%s", release))
	stepCopy := append([]string{}, steps...)
	sort.Strings(stepCopy)
	for _, step := range stepCopy {
		lines = append(lines, fmt.Sprintf("step|%s", step))
	}
	sum := sha256.Sum256([]byte(strings.Join(lines, "\n")))
	return hex.EncodeToString(sum[:])
}
DIGEST

go build -o "$APP/bin/rollbackctl" "$APP/cmd/rollbackctl"

"$APP/bin/rollbackctl" inspect
"$APP/bin/rollbackctl" plan
"$APP/bin/rollbackctl" validate

ROLLBACK_INCIDENT_ID=inc-4429 ROLLBACK_ZONE=primary bash "$APP/deploy/scripts/apply-rollback.sh"
