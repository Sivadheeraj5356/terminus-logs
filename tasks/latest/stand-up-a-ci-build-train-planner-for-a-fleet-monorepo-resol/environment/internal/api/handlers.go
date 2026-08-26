package api

import (
	"net/http"

	"github.com/fleet-ops/build-planner/internal/config"
	"github.com/fleet-ops/build-planner/internal/graph"
	"github.com/fleet-ops/build-planner/internal/registry"
	"github.com/fleet-ops/build-planner/internal/semver"
	"github.com/fleet-ops/build-planner/packages/catalog"
)

type Server struct {
	Registry     *registry.Registry
	PolicyPath   string
	ManifestPath string
	InstanceID   string
}

func (s *Server) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", s.handleHealth)
	mux.HandleFunc("/openapi.json", s.handleOpenAPI)
	mux.HandleFunc("/v1/build-plan", s.handleBuildPlan)
	mux.HandleFunc("/debug/policy", s.handleDebugPolicy)
	return mux
}

func (s *Server) loadPolicy() (config.Policy, error) {
	return config.Load(s.PolicyPath)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "method_not_allowed")
		return
	}
	id := s.InstanceID
	if id == "" {
		id = "default"
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok", "instance_id": id})
}

func (s *Server) handleOpenAPI(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "method_not_allowed")
		return
	}
	writeJSON(w, http.StatusOK, OpenAPIDoc())
}

func (s *Server) handleBuildPlan(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method_not_allowed")
		return
	}
	_, err := s.loadPolicy()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "policy_error")
		return
	}

	modules, err := catalog.LoadManifest(s.ManifestPath)
	if err != nil {
		writeError(w, http.StatusBadRequest, "manifest_error")
		return
	}

	order, err := graph.Resolve(modules)
	if err != nil {
		writeError(w, http.StatusBadRequest, "cycle_detected")
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{"modules": order})
}

func (s *Server) handleDebugPolicy(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "method_not_allowed")
		return
	}
	cfg, err := s.loadPolicy()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "policy_error")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"require_registry_approval": cfg.RequireRegistryApproval,
		"debug_endpoints_enabled":   cfg.DebugEndpointsEnabled,
		"min_module_versions":       cfg.MinModuleVersions,
		"fleet_release_pin":         cfg.FleetReleasePin,
	})
}

var _ = semver.GTE
