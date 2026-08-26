package main

import (
	"log"
	"net/http"
	"os"
	"path/filepath"

	"github.com/fleet-ops/build-planner/internal/api"
	"github.com/fleet-ops/build-planner/internal/registry"
)

func main() {
	dbPath := envOr("REGISTRY_DB_PATH", "/app/data/module-registry.json")
	policyPath := envOr("POLICY_PATH", "/app/config/fleet-policy.toml")
	manifestPath := envOr("MANIFEST_PATH", "/app/data/module-manifest.csv")
	addr := envOr("LISTEN_ADDR", "0.0.0.0:8080")
	instanceID := envOr("FLEETD_INSTANCE_ID", "default")

	if err := os.MkdirAll(filepath.Dir(dbPath), 0o755); err != nil {
		log.Fatalf("mkdir data: %v", err)
	}

	reg, err := registry.Open(dbPath)
	if err != nil {
		log.Fatalf("open registry: %v", err)
	}
	defer reg.Close()

	srv := &api.Server{
		Registry:     reg,
		PolicyPath:   policyPath,
		ManifestPath: manifestPath,
		InstanceID:   instanceID,
	}
	log.Printf("listening on %s", addr)
	if err := http.ListenAndServe(addr, srv.Routes()); err != nil {
		log.Fatalf("serve: %v", err)
	}
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
