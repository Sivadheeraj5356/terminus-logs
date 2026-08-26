package api

import (
	"net/http"
	"strings"

	"github.com/fleet-ops/build-planner/internal/attest"
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
	mux.HandleFunc("/v1/build-attest", s.handleBuildAttest)
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

func (s *Server) resolveOrder(w http.ResponseWriter) ([]string, config.Policy, bool) {
	cfg, err := s.loadPolicy()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "policy_error")
		return nil, cfg, false
	}

	modules, err := catalog.LoadManifest(s.ManifestPath)
	if err != nil {
		writeError(w, http.StatusBadRequest, "manifest_error")
		return nil, cfg, false
	}

	for _, m := range modules {
		if cfg.RequireRegistryApproval {
			status, found, err := s.Registry.Status(m.ID)
			if err != nil {
				writeError(w, http.StatusInternalServerError, "registry_error")
				return nil, cfg, false
			}
			if !found || status != "approved" {
				writeError(w, http.StatusForbidden, "module_not_allowed")
				return nil, cfg, false
			}
		}
		if min, ok := cfg.MinModuleVersions[m.ID]; ok {
			if !semver.GTE(m.Version, min) {
				writeError(w, http.StatusForbidden, "version_not_allowed")
				return nil, cfg, false
			}
		}
	}

	order, err := graph.Resolve(modules)
	if err != nil {
		msg := err.Error()
		if strings.Contains(msg, "manifest_error") {
			writeError(w, http.StatusBadRequest, "manifest_error")
			return nil, cfg, false
		}
		writeError(w, http.StatusBadRequest, "cycle_detected")
		return nil, cfg, false
	}
	return order, cfg, true
}

func (s *Server) handleBuildPlan(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method_not_allowed")
		return
	}
	order, _, ok := s.resolveOrder(w)
	if !ok {
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"modules": order})
}

func (s *Server) handleBuildAttest(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method_not_allowed")
		return
	}
	order, cfg, ok := s.resolveOrder(w)
	if !ok {
		return
	}
	digest := attest.PlanDigest(order)
	seal, err := attest.PlanSeal(digest, cfg.FleetReleasePin, uint32(len(order)))
	if err != nil {
		writeError(w, http.StatusInternalServerError, "attest_error")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"modules":     order,
		"plan_digest": digest,
		"plan_seal":   seal,
		"release_pin": cfg.FleetReleasePin,
	})
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
	if !cfg.DebugEndpointsEnabled {
		writeError(w, http.StatusNotFound, "not_found")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"require_registry_approval": cfg.RequireRegistryApproval,
		"debug_endpoints_enabled":   cfg.DebugEndpointsEnabled,
		"min_module_versions":       cfg.MinModuleVersions,
		"fleet_release_pin":         cfg.FleetReleasePin,
	})
}
