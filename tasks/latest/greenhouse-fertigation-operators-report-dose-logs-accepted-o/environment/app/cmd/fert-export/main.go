package main

import (
	"flag"
	"fmt"
	"os"

	"greenhouse-fert-gate/internal/export"
	"greenhouse-fert-gate/internal/store"
)

func main() {
	dbPath := flag.String("db", envOr("FERT_DB", "/app/data/fertigation.db"), "sqlite path")
	profilePath := flag.String("profile", "/app/config/greenhouse-profile.json", "greenhouse profile")
	outPath := flag.String("out", "/app/output/fertigation-compliance.json", "export path")
	flag.Parse()
	st, err := store.Open(*dbPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	defer st.Close()
	if err := st.Migrate("/app/migrations"); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := export.ExportCompliance(st, *profilePath, *outPath); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}
