package main

import (
	"os"

	"github.com/spf13/cobra"
)

var (
	dbPath  string
	kmsAddr string
)

var rootCmd = &cobra.Command{
	Use:   "chainaudit",
	Short: "Verify and compact the tamper-evident event log",
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		os.Exit(1)
	}
}

func init() {
	rootCmd.PersistentFlags().StringVar(&dbPath, "db", "", "path to the chainaudit SQLite database")
	rootCmd.PersistentFlags().StringVar(&kmsAddr, "kms-addr", "http://127.0.0.1:8500", "base URL of the checkpoint-signing key service")
	_ = rootCmd.MarkPersistentFlagRequired("db")
}
