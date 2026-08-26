package main

import (
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"sigproxy/internal/spool"
)

func main() {
	fs := flag.NewFlagSet("spool-inspect", flag.ExitOnError)
	dir := fs.String("dir", "state/spool", "")
	record := fs.String("record", "", "")
	sealHex := fs.String("seal-key-hex", "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef", "")
	_ = fs.Parse(os.Args[1:])

	sealKey, err := hex.DecodeString(*sealHex)
	if err != nil {
		fmt.Fprintf(os.Stderr, "invalid seal key: %v\n", err)
		os.Exit(1)
	}

	if *record != "" {
		rec, err := spool.LoadRecord(*dir, *record)
		if err != nil {
			fmt.Fprintf(os.Stderr, "load: %v\n", err)
			os.Exit(1)
		}
		printRecord(rec, sealKey)
		return
	}

	entries, err := os.ReadDir(*dir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read dir: %v\n", err)
		os.Exit(1)
	}
	for _, e := range entries {
		if filepath.Ext(e.Name()) != ".json" {
			continue
		}
		id := e.Name()[:len(e.Name())-5]
		rec, err := spool.LoadRecord(*dir, id)
		if err != nil {
			continue
		}
		printRecord(rec, sealKey)
	}
}

func printRecord(rec *spool.Record, sealKey []byte) {
	valid := spool.VerifySeal(rec, sealKey)
	out := map[string]any{
		"record_id": rec.RecordID,
		"state":     rec.State,
		"seal_valid": valid,
		"replay_count": rec.ReplayCount,
		"profile":   rec.SemanticRequest.ProfileID,
		"target":    rec.SemanticRequest.CanonicalTarget,
	}
	b, _ := json.MarshalIndent(out, "", "  ")
	fmt.Println(string(b))
}
