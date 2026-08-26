package engine

import (
	"path/filepath"
	"sort"

	"lab.local/salt_pond/internal/mast"
	"lab.local/salt_pond/internal/profile"
	"lab.local/salt_pond/pkg/pond"
	"lab.local/salt_pond/pkg/tape"
)

// ArmRow is one outward lane edge row.
type ArmRow struct {
	ArmKey      string  `json:"arm_key"`
	FrontM      float64 `json:"front_m"`
	AdvanceCmd  float64 `json:"advance_cmd"`
	SurveyM     float64 `json:"survey_m"`
	TelemetryOK bool    `json:"telemetry_ok"`
}

// DayFront is one day of survey vertices for the report.
type DayFront struct {
	Day      int `json:"day"`
	Vertices []struct {
		ArmKey string  `json:"arm_key"`
		FrontM float64 `json:"front_m"`
	} `json:"vertices"`
}

// Outcome is replay output before digest folding.
type Outcome struct {
	MastEpoch       uint32
	Arms            []ArmRow
	DailyFronts     []DayFront
	CalmLatchEvents int
	SurveyMismatch  int
	FrontSum        int
}

// ReplayOpts carries paths needed for resume and profile binding.
type ReplayOpts struct {
	AppRoot    string
	ResumePath string
}

func Replay(plan pond.Plan, arms []pond.Arm, rows []tape.Row, surveys map[string]map[int][2]float64) Outcome {
	return ReplayWith(plan, arms, rows, surveys, ReplayOpts{AppRoot: "/app"})
}

func ReplayWith(plan pond.Plan, arms []pond.Arm, rows []tape.Row, surveys map[string]map[int][2]float64, opts ReplayOpts) Outcome {
	gateOK := mast.EpochOK(plan.MastEpoch, plan.MinMastEpoch)
	mastEpoch := plan.MastEpoch
	if !gateOK {
		mastEpoch = 2
	}
	appRoot := opts.AppRoot
	if appRoot == "" {
		appRoot = "/app"
	}
	plan = profile.Bind(appRoot, plan, gateOK)

	state := map[string]*ArmRow{}
	lastCmd := map[string]float64{}
	for _, a := range arms {
		state[a.ArmKey] = &ArmRow{ArmKey: a.ArmKey, TelemetryOK: true}
		lastCmd[a.ArmKey] = 0
	}

	resumePath := opts.ResumePath
	if resumePath == "" {
		resumePath = filepath.Join(appRoot, "data", "active", "resume_state.json")
	}
	if st, ok := LoadResume(resumePath); ok {
		for k, v := range st.Fronts {
			if row, exists := state[k]; exists {
				row.FrontM = v
				row.AdvanceCmd = v
			}
		}
		// Apply resume seed before continuing the tape.
		for k := range lastCmd {
			lastCmd[k] = 0
		}
		filtered := make([]tape.Row, 0, len(rows))
		for _, row := range rows {
			if afterCursor(row.Day, row.Tick, st.CursorDay, st.CursorTick) {
				filtered = append(filtered, row)
			}
		}
		rows = filtered
		_ = st.LastCmd
	}

	calmLatch := 0
	sorted := append([]tape.Row(nil), rows...)
	sort.Slice(sorted, func(i, j int) bool {
		if sorted[i].Day == sorted[j].Day {
			return sorted[i].Tick < sorted[j].Tick
		}
		return sorted[i].Day < sorted[j].Day
	})
	for _, row := range sorted {
		_, latched := applyWindRow(plan, row, lastCmd, state)
		if latched {
			calmLatch++
		}
	}
	byDay := map[int][]tape.Row{}
	for _, row := range sorted {
		byDay[row.Day] = append(byDay[row.Day], row)
	}
	// Include survey days even when tape suffix is empty of a day key from resume.
	for _, days := range surveys {
		for day := range days {
			if _, ok := byDay[day]; !ok {
				byDay[day] = nil
			}
		}
	}
	daily := make([]DayFront, 0, len(byDay))
	for day := range byDay {
		df := DayFront{Day: day}
		for _, a := range arms {
			if sv, ok := surveys[a.ArmKey][day]; ok {
				df.Vertices = append(df.Vertices, struct {
					ArmKey string  `json:"arm_key"`
					FrontM float64 `json:"front_m"`
				}{ArmKey: a.ArmKey, FrontM: sv[0]})
			}
		}
		daily = append(daily, df)
	}
	sort.Slice(daily, func(i, j int) bool { return daily[i].Day < daily[j].Day })

	mismatch, frontSum := finalizeSurvey(arms, state, surveys, plan.SurveyLayer)
	outArms := make([]ArmRow, 0, len(arms))
	for _, a := range arms {
		outArms = append(outArms, *state[a.ArmKey])
	}
	return Outcome{
		MastEpoch:       mastEpoch,
		Arms:            outArms,
		DailyFronts:     daily,
		CalmLatchEvents: calmLatch,
		SurveyMismatch:  mismatch,
		FrontSum:        frontSum,
	}
}
