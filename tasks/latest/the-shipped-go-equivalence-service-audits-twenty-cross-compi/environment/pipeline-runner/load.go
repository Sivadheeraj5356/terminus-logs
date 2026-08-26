package runner

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"artifactequiv/artifact-registry"
	"artifactequiv/equivalence-engine"
)

func sessionDir() string {
	if d := os.Getenv("EQUIV_SESSION_DIR"); d != "" {
		return d
	}
	return "/app/build-sessions"
}

func sessionPaths() ([]string, error) {
	dir := sessionDir()
	paths := make([]string, 0, 20)
	for i := 1; i <= 20; i++ {
		paths = append(paths, filepath.Join(dir, fmt.Sprintf("build_%02d.json", i)))
	}
	return paths, nil
}

// Run loads bundled sessions and builds the equivalence report.
func Run() (registry.Report, error) {
	paths, err := sessionPaths()
	if err != nil {
		return registry.Report{}, err
	}

	var sessions []registry.SessionResult
	summary := registry.Summary{SessionsAnalyzed: 20}

	for _, p := range paths {
		raw, err := os.ReadFile(p)
		if err != nil {
			return registry.Report{}, err
		}
		var sf engine.SessionFile
		if err := json.Unmarshal(raw, &sf); err != nil {
			return registry.Report{}, err
		}
		res := engine.EvaluateSession(sf)
		sessions = append(sessions, res)
		if res.Equivalent {
			summary.EquivalentSessions++
		} else {
			summary.DivergentSessions++
		}
		summary.TotalDivergencesFound += len(res.Divergences)
		summary.StressSchedulesRun += res.Stress.SchedulesRun
		summary.StressSchedulesPassed += res.Stress.SchedulesPassed
	}

	sort.Slice(sessions, func(i, j int) bool {
		return sessions[i].SessionID < sessions[j].SessionID
	})

	return registry.Report{Summary: summary, Sessions: sessions}, nil
}
