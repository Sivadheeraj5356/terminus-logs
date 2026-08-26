package main

import (
	"flag"
	"fmt"
	"os"

	"greenhouse-fert-gate/internal/ingest"
	"greenhouse-fert-gate/internal/store"
)

func main() {
	dbPath := flag.String("db", envOr("FERT_DB", "/app/data/fertigation.db"), "sqlite path")
	eventsPath := flag.String("events", "", "jsonl events file")
	profilePath := flag.String("profile", "/app/config/greenhouse-profile.json", "greenhouse profile")
	flag.Parse()
	if *eventsPath == "" {
		fmt.Fprintln(os.Stderr, "missing --events")
		os.Exit(2)
	}
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
	if err := ingest.IngestFilePath(st, *eventsPath, *profilePath); err != nil {
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
