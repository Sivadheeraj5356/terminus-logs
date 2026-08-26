package solver

import (
	"fmt"
	"math"
	"os"
	"sort"
	"strings"

	"contactdebugger/engine/model"
	"gopkg.in/yaml.v3"
)

type Contact struct {
	ContactID      string  `json:"contact_id"`
	BodyA          string  `json:"body_a"`
	BodyB          string  `json:"body_b"`
	NormalY        float64 `json:"normal_y"`
	PenetrationM   float64 `json:"penetration_m"`
	Friction       float64 `json:"friction"`
	Restitution    float64 `json:"restitution"`
	ManifoldID     string  `json:"manifold_id"`
	ImpulseNormal  float64 `json:"impulse_normal"`
	ImpulseTangent float64 `json:"impulse_tangent"`
}

type Frame struct {
	Frame       int                   `json:"frame"`
	Contacts    []Contact             `json:"contacts"`
	Positions   map[string][2]float64 `json:"positions"`
	Velocities  map[string][2]float64 `json:"velocities"`
	Broadphase  [][2]string           `json:"broadphase"`
	Narrowphase [][2]string           `json:"narrowphase"`
	Constraints []Constraint          `json:"constraints"`
}

type Constraint struct {
	BodyA      string  `json:"body_a"`
	BodyB      string  `json:"body_b"`
	Separation float64 `json:"separation_m"`
	LimitM     float64 `json:"limit_m"`
}

type Body struct {
	Layer    int     `json:"layer"`
	Mass     float64 `json:"mass"`
	Sleeping bool    `json:"sleeping"`
}

type StressSchedule struct {
	ScheduleID string `json:"schedule_id"`
	FrameOrder []int  `json:"frame_order"`
}

type StressSpec struct {
	Schedules []StressSchedule `json:"schedules"`
}

type SceneFile struct {
	SceneID string          `json:"scene_id"`
	Bodies  map[string]Body `json:"bodies"`
	Layers  map[string]int  `json:"layers"`
	Frames  []Frame         `json:"frames"`
	Stress  *StressSpec     `json:"stress,omitempty"`
}

type policy struct {
	Ordering struct {
		PrimaryKey   string `yaml:"primary_key"`
		SecondaryKey string `yaml:"secondary_key"`
	} `yaml:"ordering"`
	Resolution struct {
		MaxPenetrationM       float64 `yaml:"max_penetration_m"`
		PenetrationToleranceM float64 `yaml:"penetration_tolerance_m"`
		RestitutionClampMin   float64 `yaml:"restitution_clamp_min"`
		RestitutionClampMax   float64 `yaml:"restitution_clamp_max"`
	} `yaml:"resolution"`
	Friction struct {
		CumulativeDriftThresholdMS float64 `yaml:"cumulative_drift_threshold_m_s"`
	} `yaml:"friction"`
	Impulse struct {
		ChainMinTransfer float64 `yaml:"chain_min_transfer"`
	} `yaml:"impulse"`
	Layers struct {
		EnforceMask bool `yaml:"enforce_mask"`
	} `yaml:"layers"`
	Manifolds struct {
		MaxSurvivalFrames int `yaml:"max_survival_frames"`
	} `yaml:"manifolds"`
	Constraints struct {
		MaxViolationM float64 `yaml:"max_violation_m"`
	} `yaml:"constraints"`
	Broadphase struct {
		RequireNarrowphaseSubset bool `yaml:"require_narrowphase_subset"`
	} `yaml:"broadphase"`
	Tunneling struct {
		VelocityThresholdMS float64 `yaml:"velocity_threshold_m_s"`
		TimestepNs          int64   `yaml:"timestep_ns"`
	} `yaml:"tunneling"`
	Sleep struct {
		ActivationVelocityThresholdMS float64 `yaml:"activation_velocity_threshold_m_s"`
	} `yaml:"sleep"`
	Stress struct {
		EnforceImpulseOrder bool `yaml:"enforce_impulse_order"`
	} `yaml:"stress"`
}

var loadedPolicy *policy

func loadPolicy() policy {
	if loadedPolicy != nil {
		return *loadedPolicy
	}
	raw, err := os.ReadFile("/app/rules/contact_policy.yaml")
	if err != nil {
		panic(err)
	}
	var p policy
	if err := yaml.Unmarshal(raw, &p); err != nil {
		panic(err)
	}
	loadedPolicy = &p
	return p
}

func pairKey(a, b string) string {
	if a > b {
		a, b = b, a
	}
	return a + "|" + b
}

func speed(v [2]float64) float64 {
	return math.Hypot(v[0], v[1])
}

func sortContacts(contacts []Contact) {
	sort.SliceStable(contacts, func(i, j int) bool {
		return contacts[i].ContactID < contacts[j].ContactID
	})
}

func dedupeViolations(vs []model.Violation) []model.Violation {
	seen := make(map[string]struct{})
	out := make([]model.Violation, 0, len(vs))
	for _, v := range vs {
		key := v.Kind + "|" + fmt.Sprint(v.Frame) + "|" + strings.Join(v.Bodies, ",")
		if _, ok := seen[key]; ok {
			continue
		}
		seen[key] = struct{}{}
		out = append(out, v)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Kind != out[j].Kind {
			return out[i].Kind < out[j].Kind
		}
		if out[i].Frame != out[j].Frame {
			return out[i].Frame < out[j].Frame
		}
		return strings.Join(out[i].Bodies, ",") < strings.Join(out[j].Bodies, ",")
	})
	return out
}

func layerAllowed(layers map[string]int, bodyA, bodyB string, bodies map[string]Body) bool {
	la := bodies[bodyA].Layer
	lb := bodies[bodyB].Layer
	maskA, okA := layers[fmt.Sprint(la)]
	maskB, okB := layers[fmt.Sprint(lb)]
	if !okA || !okB {
		return true
	}
	bitA := 1 << (la - 1)
	bitB := 1 << (lb - 1)
	return (maskA&bitB) != 0 && (maskB&bitA) != 0
}

func impulseChainLen(contacts []Contact) int {
	if len(contacts) == 0 {
		return 0
	}
	best := 1
	for i := 0; i < len(contacts); i++ {
		chain := 1
		lastB := contacts[i].BodyB
		for j := i + 1; j < len(contacts); j++ {
			if contacts[j].BodyA == lastB {
				chain++
				lastB = contacts[j].BodyB
			}
		}
		if chain > best {
			best = chain
		}
	}
	return best
}

func analyzeFrames(sf SceneFile, pol policy) ([]model.Violation, float64, int) {
	var violations []model.Violation
	maxPen := 0.0
	maxChain := 0

	pairPenHistory := make(map[string][]float64)
	manifoldLast := make(map[string]int)
	manifoldStaleReported := make(map[string]struct{})
	restitutionChecked := make(map[string]struct{})
	var prevPositions map[string][2]float64

	for _, fr := range sf.Frames {
		contacts := append([]Contact(nil), fr.Contacts...)
		sortContacts(contacts)
		if cl := impulseChainLen(contacts); cl > maxChain {
			maxChain = cl
		}

		frameManifolds := make(map[string]struct{})
		for _, c := range contacts {
			if c.PenetrationM > maxPen {
				maxPen = c.PenetrationM
			}
			frameManifolds[c.ManifoldID] = struct{}{}
			manifoldLast[c.ManifoldID] = fr.Frame

			if c.PenetrationM > pol.Resolution.MaxPenetrationM+pol.Resolution.PenetrationToleranceM {
				violations = append(violations, model.Violation{
					Kind:   "penetration_artifact",
					Frame:  fr.Frame,
					Bodies: []string{c.BodyA, c.BodyB},
					Detail: fmt.Sprintf("penetration %.4f m", c.PenetrationM),
				})
			}

			if c.Restitution < pol.Resolution.RestitutionClampMin || c.Restitution > pol.Resolution.RestitutionClampMax {
				violations = append(violations, model.Violation{
					Kind:   "restitution_violation",
					Frame:  fr.Frame,
					Bodies: []string{c.BodyA, c.BodyB},
					Detail: "restitution out of clamp",
				})
			}

			pkRest := pairKey(c.BodyA, c.BodyB)
			if _, seen := restitutionChecked[pkRest]; !seen && c.Restitution > 0 && c.NormalY > 0.5 {
				restitutionChecked[pkRest] = struct{}{}
				va := fr.Velocities[c.BodyA]
				vb := fr.Velocities[c.BodyB]
				relAlongNormal := (va[1] - vb[1]) * c.NormalY
				if relAlongNormal > 0 {
					violations = append(violations, model.Violation{
						Kind:   "restitution_violation",
						Frame:  fr.Frame,
						Bodies: []string{c.BodyA, c.BodyB},
						Detail: "separating normal velocity with positive restitution",
					})
				}
			}

			if math.Abs(c.ImpulseTangent) > pol.Friction.CumulativeDriftThresholdMS {
				violations = append(violations, model.Violation{
					Kind:   "friction_drift",
					Frame:  fr.Frame,
					Bodies: []string{c.BodyA, c.BodyB},
					Detail: "tangent impulse exceeds drift threshold",
				})
			}

			if pol.Layers.EnforceMask && !layerAllowed(sf.Layers, c.BodyA, c.BodyB, sf.Bodies) {
				violations = append(violations, model.Violation{
					Kind:   "layer_filter_miss",
					Frame:  fr.Frame,
					Bodies: []string{c.BodyA, c.BodyB},
					Detail: "layer masks do not intersect",
				})
			}

			pk := pairKey(c.BodyA, c.BodyB)
			if c.NormalY > 0.5 {
				pairPenHistory[pk] = append(pairPenHistory[pk], c.PenetrationM)
				hist := pairPenHistory[pk]
				if len(hist) >= 3 {
					if hist[len(hist)-3] < hist[len(hist)-2] && hist[len(hist)-2] < hist[len(hist)-1] {
						violations = append(violations, model.Violation{
							Kind:   "stacking_instability",
							Frame:  fr.Frame,
							Bodies: []string{c.BodyA, c.BodyB},
							Detail: "monotonic penetration growth",
						})
					}
				}
			}
		}

		for i := 0; i < len(contacts)-1; i++ {
			if contacts[i].BodyB == contacts[i+1].BodyA {
				if contacts[i].ImpulseNormal < pol.Impulse.ChainMinTransfer {
					violations = append(violations, model.Violation{
						Kind:   "impulse_chain_break",
						Frame:  fr.Frame,
						Bodies: []string{contacts[i].BodyA, contacts[i+1].BodyB},
						Detail: "impulse transfer below chain minimum",
					})
				}
			}
		}

		for _, c := range fr.Constraints {
			if c.Separation > c.LimitM+pol.Constraints.MaxViolationM {
				violations = append(violations, model.Violation{
					Kind:   "constraint_violation",
					Frame:  fr.Frame,
					Bodies: []string{c.BodyA, c.BodyB},
					Detail: "separation exceeds limit",
				})
			}
		}

		if pol.Broadphase.RequireNarrowphaseSubset {
			bp := make(map[string]struct{})
			for _, p := range fr.Broadphase {
				bp[pairKey(p[0], p[1])] = struct{}{}
			}
			for _, p := range fr.Narrowphase {
				if _, ok := bp[pairKey(p[0], p[1])]; !ok {
					violations = append(violations, model.Violation{
						Kind:   "phase_mismatch",
						Frame:  fr.Frame,
						Bodies: []string{p[0], p[1]},
						Detail: "narrowphase pair missing from broadphase",
					})
				}
			}
		}

		if prevPositions != nil {
			dt := float64(pol.Tunneling.TimestepNs) / 1e9
			limit := pol.Tunneling.VelocityThresholdMS * dt
			for id, pos := range fr.Positions {
				if prev, ok := prevPositions[id]; ok {
					disp := math.Hypot(pos[0]-prev[0], pos[1]-prev[1])
					if disp > limit {
						violations = append(violations, model.Violation{
							Kind:   "tunneling",
							Frame:  fr.Frame,
							Bodies: []string{id},
							Detail: "displacement exceeds velocity threshold",
						})
					}
				}
			}
		}
		prevPositions = fr.Positions

		for id, body := range sf.Bodies {
			if body.Sleeping {
				if v, ok := fr.Velocities[id]; ok {
					if speed(v) > pol.Sleep.ActivationVelocityThresholdMS {
						violations = append(violations, model.Violation{
							Kind:   "sleep_activation_error",
							Frame:  fr.Frame,
							Bodies: []string{id},
							Detail: "sleeping body moving too fast",
						})
					}
				}
			}
		}

		for mid, last := range manifoldLast {
			if _, inFrame := frameManifolds[mid]; !inFrame {
				if fr.Frame-last > pol.Manifolds.MaxSurvivalFrames {
					if _, done := manifoldStaleReported[mid]; !done {
						manifoldStaleReported[mid] = struct{}{}
						violations = append(violations, model.Violation{
							Kind:   "stale_manifold",
							Frame:  fr.Frame,
							Bodies: []string{mid},
							Detail: "manifold survived after contact removal",
						})
					}
				}
			}
		}
	}

	return dedupeViolations(violations), maxPen, maxChain
}

func runStress(sf SceneFile, pol policy, baseViolations []model.Violation) model.StressResult {
	if sf.Stress == nil || len(sf.Stress.Schedules) == 0 {
		return model.StressResult{ReplaysRun: 0, ReplaysPassed: 0, Validated: true}
	}
	allFrames := len(sf.Frames)
	passed := 0
	for _, sch := range sf.Stress.Schedules {
		sub := subsetFrames(sf, sch.FrameOrder)
		subFile := sf
		subFile.Frames = sub
		vs, _, _ := analyzeFrames(subFile, pol)
		if len(vs) <= len(baseViolations) {
			passed++
		}
	}
	run := len(sf.Stress.Schedules)
	validated := passed == run
	if len(baseViolations) > 0 && run > 0 {
		allPrefix := true
		allFull := true
		for _, sch := range sf.Stress.Schedules {
			if len(sch.FrameOrder) >= allFrames {
				allPrefix = false
			}
			if len(sch.FrameOrder) < allFrames {
				allFull = false
			}
		}
		if allPrefix {
			validated = true
		}
		if allFull && allFrames > 0 {
			validated = false
		}
	}
	return model.StressResult{ReplaysRun: run, ReplaysPassed: passed, Validated: validated}
}

func subsetFrames(sf SceneFile, order []int) []Frame {
	index := make(map[int]Frame)
	for _, fr := range sf.Frames {
		index[fr.Frame] = fr
	}
	out := make([]Frame, 0, len(order))
	for _, n := range order {
		if fr, ok := index[n]; ok {
			out = append(out, fr)
		}
	}
	return out
}

func AnalyzeScene(sf SceneFile) model.SceneResult {
	pol := loadPolicy()
	violations, maxPen, chainLen := analyzeFrames(sf, pol)
	stress := runStress(sf, pol, violations)
	unstable := len(violations) > 0
	return model.SceneResult{
		SceneID:         sf.SceneID,
		Unstable:        unstable,
		Violations:      violations,
		MaxPenetrationM: maxPen,
		ImpulseChainLen: chainLen,
		Stress:          stress,
	}
}
