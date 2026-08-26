#!/usr/bin/env bash
set -euo pipefail

python3 <<'PY'
from pathlib import Path

base = Path("/app/environment")


def patch(rel: str, old: str, new: str) -> None:
    path = base / rel
    text = path.read_text()
    if old not in text:
        raise SystemExit(f"missing anchor in {rel}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1))


Path("/app/environment/internal/aura/stack.go").write_text(
    """package aura

type LaneTag int

const (
	LanePrimary LaneTag = iota
	LaneSecondary
)

type AuraBuf struct {
	Magnitude int
	Duration  int
	StackID   int
}

type AuraSpec struct {
	MagnitudeDelta int
	DurationDelta  int
	Lane           LaneTag
}

type StackOutcome struct {
	Magnitude int
	Duration  int
	StackID   int
}

type LaneCoef struct {
	Primary   int
	Secondary int
}

func laneWeight(lane LaneTag, coef LaneCoef) int {
	if lane == LanePrimary {
		return coef.Primary
	}
	return coef.Secondary
}

func StackMerge(buf AuraBuf, incoming AuraSpec, lane LaneTag, coef LaneCoef) StackOutcome {
	newMagnitude := buf.Magnitude + incoming.MagnitudeDelta
	newDuration := buf.Duration + incoming.DurationDelta
	weight := laneWeight(lane, coef)
	mixed := buf.StackID ^ incoming.MagnitudeDelta
	return StackOutcome{
		Magnitude: newMagnitude,
		Duration:  newDuration,
		StackID:   mixed + newDuration + weight,
	}
}
"""
)

Path("/app/environment/internal/pulse/plan.go").write_text(
    """package pulse

type TickProfile int

const (
	ProfileStrict TickProfile = iota
	ProfileLoose
)

func (p TickProfile) Label() string {
	if p == ProfileStrict {
		return "strict_tick"
	}
	return "loose_tick"
}

func ParseProfile(label string) TickProfile {
	if label == "loose_tick" {
		return ProfileLoose
	}
	return ProfileStrict
}

type IFrameCtr struct {
	Active       bool
	OverlapTicks int
}

type TickSched struct {
	Tick          int
	PulsePeriod   int
	PendingDamage int
}

type PulsePlan struct {
	FireNow    bool
	Deferred   int
	PulseCount int
}

func PlanPulse(sched TickSched, profile TickProfile, iframe IFrameCtr) PulsePlan {
	onBoundary := sched.Tick > 0 && sched.Tick%sched.PulsePeriod == 0
	if !onBoundary {
		return PulsePlan{FireNow: false, Deferred: sched.PendingDamage, PulseCount: 0}
	}
	if iframe.Active && iframe.OverlapTicks > 0 {
		return PulsePlan{
			FireNow:    false,
			Deferred:   sched.PendingDamage + sched.PulsePeriod,
			PulseCount: 0,
		}
	}
	if profile == ProfileLoose && sched.PendingDamage > sched.PulsePeriod {
		return PulsePlan{
			FireNow:    false,
			Deferred:   sched.PendingDamage,
			PulseCount: 0,
		}
	}
	return PulsePlan{
		FireNow:    true,
		Deferred:   0,
		PulseCount: sched.PendingDamage + 1,
	}
}
"""
)

Path("/app/environment/internal/settle/rule.go").write_text(
    """package settle

type ActorPair struct {
	EntityA     int
	EntityB     int
	ActionOrder [2]int
}

type OutcomeState struct {
	HPA      int
	HPB      int
	Settled  bool
	WinnerID int
}

type SettleVerdict struct {
	State   OutcomeState
	TieStep int
}

func singleLethalWinner(actors ActorPair, lethalA, lethalB bool) int {
	if lethalA && !lethalB {
		return actors.EntityA
	}
	if lethalB && !lethalA {
		return actors.EntityB
	}
	return -1
}

func ApplySettle(state OutcomeState, actors ActorPair, stepID int) SettleVerdict {
	if state.Settled {
		return SettleVerdict{State: state, TieStep: stepID}
	}
	lethalA := state.HPA <= 0
	lethalB := state.HPB <= 0
	if lethalA && lethalB {
		winner := actors.EntityA
		if actors.EntityB < winner {
			winner = actors.EntityB
		}
		return SettleVerdict{
			State: OutcomeState{
				HPA:      state.HPA,
				HPB:      state.HPB,
				Settled:  true,
				WinnerID: winner,
			},
			TieStep: stepID,
		}
	}
	winner := singleLethalWinner(actors, lethalA, lethalB)
	if winner >= 0 {
		return SettleVerdict{
			State: OutcomeState{
				HPA:      state.HPA,
				HPB:      state.HPB,
				Settled:  true,
				WinnerID: winner,
			},
			TieStep: stepID,
		}
	}
	return SettleVerdict{State: state, TieStep: stepID}
}
"""
)

patch(
    "internal/persist/state.go",
    """\tvar st SettleState
\tif err := json.Unmarshal(raw, &st); err != nil {
\t\treturn SettleState{}, err
\t}
\tif last, ok, jerr := lastJournalResidue(); jerr == nil && ok {
\t\tst.PulseCarry = last
\t}
\treturn st, nil
""",
    """\tvar st SettleState
\tif err := json.Unmarshal(raw, &st); err != nil {
\t\treturn SettleState{}, err
\t}
\treturn st, nil
""",
)

patch(
    "internal/replay/driver.go",
    """func RunManifest(spec ScenarioSpec, profile pulse.TickProfile, depthLimit int, coef aura.LaneCoef) (map[string]any, error) {
\traw, err := os.ReadFile(filepath.Join(EvDir, spec.EvBin))
""",
    """func RunManifest(spec ScenarioSpec, profile pulse.TickProfile, depthLimit int, coef aura.LaneCoef) (map[string]any, error) {
\tstored, err := persist.LoadState()
\tif err != nil {
\t\treturn nil, err
\t}
\tif err := persist.SaveState(persist.SettleState{Poisoned: stored.Poisoned, PulseCarry: 0}); err != nil {
\t\treturn nil, err
\t}
\traw, err := os.ReadFile(filepath.Join(EvDir, spec.EvBin))
""",
)

patch(
    "internal/replay/driver.go",
    """\tsortedDigests := append([]string{}, digests...)
\tsort.Strings(sortedDigests)
\tjoined := ""
\tfor _, d := range sortedDigests {
\t\tjoined += d
\t}
\tcross := sha256.Sum256([]byte(joined))
""",
    """\tjoined := ""
\tfor _, d := range digests {
\t\tjoined += d
\t}
\tcross := sha256.Sum256([]byte(joined))
""",
)

drv_path = base / "internal/replay/driver.go"
drv = drv_path.read_text()
if "\t\"sort\"\n" in drv and "sort." not in drv:
    drv_path.write_text(drv.replace("\t\"sort\"\n", ""))

patch(
    "internal/fold/matrix.go",
    """\tvar cleanRuns []RunRow
\tfor _, row := range runs {
\t\tclean := RunRow{}
\t\tfor k, v := range row {
\t\t\tif k == "violations" {
\t\t\t\tcontinue
\t\t\t}
\t\t\tclean[k] = v
\t\t}
\t\tcleanRuns = append(cleanRuns, clean)
\t}

\tstampPayload, err := json.Marshal(cleanRuns)
\tif err != nil {
\t\treturn Matrix{}, err
\t}
\tsum := sha256.Sum256(stampPayload)
\tstamp := hex.EncodeToString(sum[:])[:16]
""",
    """\tstampPayload, err := json.Marshal(runs)
\tif err != nil {
\t\treturn Matrix{}, err
\t}
\tsum := sha256.Sum256(stampPayload)
\tstamp := hex.EncodeToString(sum[:])[:16]

\tvar cleanRuns []RunRow
\tfor _, row := range runs {
\t\tclean := RunRow{}
\t\tfor k, v := range row {
\t\t\tif k == "violations" {
\t\t\t\tcontinue
\t\t\t}
\t\t\tclean[k] = v
\t\t}
\t\tcleanRuns = append(cleanRuns, clean)
\t}
""",
)

Path("/app/environment/migrations/cln7.sh").write_text(
    """#!/usr/bin/env bash
set -euo pipefail
settle_file="/app/var/lab/settle_state.json"
journal_file="/app/var/lab/pulse_journal.jsonl"
mkdir -p /app/var/lab
if [[ "${1:-}" == "--restore" && -n "${2:-}" ]]; then
  cp "$2" "$settle_file"
  : > "$journal_file"
  exit 0
fi
rm -f "$settle_file"
echo '{"poisoned": true, "pulse_carry": 255}' > "$settle_file"
: > "$journal_file"
"""
)
Path("/app/environment/migrations/cln7.sh").chmod(0o755)
PY

bash /app/environment/scripts/build_lab.sh
/app/bin/mdl_lab --full-matrix --depth 5 --out /app/output/cmb_out.json
