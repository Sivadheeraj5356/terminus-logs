package main

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"

	"chainaudit/internal/audit"
	"chainaudit/internal/store"
)

var (
	compactOut     string
	compactNowFile string
)

var compactCmd = &cobra.Command{
	Use:   "compact",
	Short: "Prune expired, fully-checkpointed events from the database",
	RunE:  runCompact,
}

func init() {
	compactCmd.Flags().StringVar(&compactOut, "out", "", "path to write compact_manifest.json")
	compactCmd.Flags().StringVar(&compactNowFile, "now-file", "", "path to a file containing the reference unix timestamp to prune against")
	_ = compactCmd.MarkFlagRequired("out")
	_ = compactCmd.MarkFlagRequired("now-file")
	rootCmd.AddCommand(compactCmd)
}

func runCompact(cmd *cobra.Command, args []string) error {
	now, err := readNow(compactNowFile)
	if err != nil {
		return fmt.Errorf("read now-file: %w", err)
	}

	st, err := store.Open(dbPath)
	if err != nil {
		return fmt.Errorf("open db: %w", err)
	}
	defer st.Close()

	streams, err := st.Streams()
	if err != nil {
		return fmt.Errorf("list streams: %w", err)
	}

	manifest := audit.CompactManifest{DBPath: dbPath, Now: now}

	for i := range streams {
		s := &streams[i]
		events, err := st.Events(s.StreamID)
		if err != nil {
			return fmt.Errorf("list events for %s: %w", s.StreamID, err)
		}
		checkpoints, err := st.Checkpoints(s.StreamID)
		if err != nil {
			return fmt.Errorf("list checkpoints for %s: %w", s.StreamID, err)
		}
		sm, err := audit.CompactStream(st, s, events, checkpoints, now)
		if err != nil {
			return fmt.Errorf("compact %s: %w", s.StreamID, err)
		}
		manifest.Streams = append(manifest.Streams, sm)
	}

	return writeJSON(compactOut, manifest)
}

func readNow(path string) (int64, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return 0, err
	}
	var now int64
	_, err = fmt.Sscanf(string(data), "%d", &now)
	return now, err
}
