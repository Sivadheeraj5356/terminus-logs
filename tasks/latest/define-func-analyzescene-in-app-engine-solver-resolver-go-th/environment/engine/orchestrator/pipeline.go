package orchestrator

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"contactdebugger/engine/model"
	"contactdebugger/engine/solver"
)

func sceneDir() string {
	if d := os.Getenv("PHYSICS_SCENE_DIR"); d != "" {
		return d
	}
	return "/app/scenarios"
}

func scenePaths() ([]string, error) {
	dir := sceneDir()
	paths := make([]string, 0, 20)
	for i := 1; i <= 20; i++ {
		paths = append(paths, filepath.Join(dir, fmt.Sprintf("scene_%02d.json", i)))
	}
	return paths, nil
}

func Run() (model.Report, error) {
	paths, err := scenePaths()
	if err != nil {
		return model.Report{}, err
	}

	var scenes []model.SceneResult
	summary := model.Summary{ScenesAnalyzed: 20}

	for _, p := range paths {
		raw, err := os.ReadFile(p)
		if err != nil {
			return model.Report{}, err
		}
		var sf solver.SceneFile
		if err := json.Unmarshal(raw, &sf); err != nil {
			return model.Report{}, err
		}
		res := solver.AnalyzeScene(sf)
		scenes = append(scenes, res)
		if res.Unstable {
			summary.UnstableScenes++
			summary.TotalViolations += len(res.Violations)
		} else {
			summary.StableScenes++
		}
		summary.StressReplaysRun += res.Stress.ReplaysRun
		summary.StressReplaysPassed += res.Stress.ReplaysPassed
	}

	return model.Report{Summary: summary, Scenes: scenes}, nil
}
