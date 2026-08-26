package feeder

import (
	"path/filepath"

	"jwksbound.local/mux/model"
)

func StateDir(profile string) string {
	return filepath.Join(model.OutDir, "state", profile)
}

func PathFor(profile, name string) string {
	return filepath.Join(StateDir(profile), name)
}
