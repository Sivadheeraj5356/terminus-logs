package main

import (
	"fmt"
	"os"

	"github.com/acme/auth/internal/audit"
	"github.com/acme/auth/internal/clock"
	"github.com/acme/auth/internal/config"
	"github.com/acme/auth/internal/jwk"
	"github.com/acme/auth/internal/ledger"
	"github.com/acme/auth/internal/validator"
)

const configPath = "/app/auth/config/service.toml"

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: tokensvc <validate|revoke|export-audit> ...")
		os.Exit(2)
	}
	cfg, err := config.Load(configPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	clk := clock.New(cfg)
	state, err := jwk.LoadRotationState(cfg.Service.RotationState)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	keys, err := jwk.LoadPublished(cfg.Service.KeysDir, state, clk.NowUnix(), cfg.Rotation.GraceSeconds)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	led, err := ledger.Open(cfg.Service.DBPath, clk)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	defer led.Close()

	switch os.Args[1] {
	case "validate":
		if len(os.Args) != 3 {
			os.Exit(2)
		}
		v := validator.NewLifecycle(keys, led, clk)
		if _, err := v.Validate(os.Args[2]); err != nil {
			os.Exit(1)
		}
	case "revoke":
		if len(os.Args) < 3 {
			os.Exit(2)
		}
		reason := ""
		if len(os.Args) > 3 {
			reason = os.Args[3]
		}
		if err := led.Revoke(os.Args[2], reason); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	case "export-audit":
		exp := audit.New(clk, state, led, cfg.Service.AuditOut)
		if err := exp.Write(); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	default:
		os.Exit(2)
	}
}
