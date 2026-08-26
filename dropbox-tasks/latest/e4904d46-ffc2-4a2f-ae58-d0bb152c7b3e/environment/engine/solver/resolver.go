package solver

import "contactdebugger/engine/model"

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
	Frame        int                `json:"frame"`
	Contacts     []Contact          `json:"contacts"`
	Positions    map[string][2]float64 `json:"positions"`
	Velocities   map[string][2]float64 `json:"velocities"`
	Broadphase   [][2]string        `json:"broadphase"`
	Narrowphase  [][2]string        `json:"narrowphase"`
	Constraints  []Constraint       `json:"constraints"`
}

type Constraint struct {
	BodyA      string  `json:"body_a"`
	BodyB      string  `json:"body_b"`
	Separation float64 `json:"separation_m"`
	LimitM     float64 `json:"limit_m"`
}

type Body struct {
	Layer    int  `json:"layer"`
	Mass     float64 `json:"mass"`
	Sleeping bool `json:"sleeping"`
}

type StressSchedule struct {
	ScheduleID    string `json:"schedule_id"`
	FrameOrder    []int  `json:"frame_order"`
}

type StressSpec struct {
	Schedules []StressSchedule `json:"schedules"`
}

type SceneFile struct {
	SceneID string         `json:"scene_id"`
	Bodies  map[string]Body `json:"bodies"`
	Layers  map[string]int `json:"layers"`
	Frames  []Frame        `json:"frames"`
	Stress  *StressSpec    `json:"stress,omitempty"`
}

// AnalyzeScene replays contact frames, evaluates stability rules, and runs stress replays.
func AnalyzeScene(sf SceneFile) model.SceneResult {
	panic("solver.AnalyzeScene not implemented")
}
