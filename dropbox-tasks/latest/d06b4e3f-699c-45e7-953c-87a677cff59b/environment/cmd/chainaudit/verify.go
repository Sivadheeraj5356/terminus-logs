package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/cobra"

	"chainaudit/internal/audit"
	"chainaudit/internal/kms"
	"chainaudit/internal/store"
)

var verifyOut string

var verifyCmd = &cobra.Command{
	Use:   "verify",
	Short: "Verify the integrity of every stream in the database",
	RunE:  runVerify,
}

func init() {
	verifyCmd.Flags().StringVar(&verifyOut, "out", "", "path to write verify_report.json")
	_ = verifyCmd.MarkFlagRequired("out")
	rootCmd.AddCommand(verifyCmd)
}

func runVerify(cmd *cobra.Command, args []string) error {
	st, err := store.Open(dbPath)
	if err != nil {
		return fmt.Errorf("open db: %w", err)
	}
	defer st.Close()

	streams, err := st.Streams()
	if err != nil {
		return fmt.Errorf("list streams: %w", err)
	}

	kmsClient := kms.NewClient(kmsAddr)
	ctx := context.Background()

	report := audit.VerifyReport{DBPath: dbPath}

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
		report.Streams = append(report.Streams, audit.VerifyStream(ctx, kmsClient, s, events, checkpoints))
	}

	report.ChainTipHashAll = audit.OverallChainTip(report.Streams)

	return writeJSON(verifyOut, report)
}

func writeJSON(path string, v interface{}) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	enc := json.NewEncoder(f)
	enc.SetIndent("", "  ")
	return enc.Encode(v)
}
