package main

import (
	"flag"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"sigproxy/internal/config"
	"sigproxy/internal/keyring"
	"sigproxy/internal/proxy"
	"sigproxy/internal/spool"
	"sigproxy/internal/trace"
	"sigproxy/internal/audit"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	switch os.Args[1] {
	case "serve":
		os.Exit(runServe(os.Args[2:]))
	case "recover":
		os.Exit(runRecover(os.Args[2:]))
	default:
		usage()
		os.Exit(2)
	}
}

func usage() {
	fmt.Fprintf(os.Stderr, "usage: proxy-local serve|recover [flags]\n")
}

func runServe(args []string) int {
	fs := flag.NewFlagSet("serve", flag.ExitOnError)
	listen := fs.String("listen-unix", "", "")
	backend := fs.String("backend-unix", "", "")
	cfgPath := fs.String("config", "config/proxy.json", "")
	profiles := fs.String("profiles", "", "")
	keyringPath := fs.String("keyring", "", "")
	stateDir := fs.String("state-dir", "", "")
	auditLog := fs.String("audit-log", "", "")
	tracePath := fs.String("trace", "/output/request-trace.json", "")
	ready := fs.String("ready-file", "", "")
	_ = fs.Parse(args)

	rt, err := loadRuntime(*cfgPath, *profiles, *keyringPath, *stateDir, *auditLog, *tracePath, *listen, *backend, *ready)
	if err != nil {
		fmt.Fprintf(os.Stderr, "init: %v\n", err)
		return 1
	}

	if rt.Config.ReplayOnStart {
		traceW := trace.NewWriter(rt.Config.TracePath, "serve-replay", rt.Catalog.CatalogDigest)
		auditW := audit.NewSnapshotWriter(rt.Config.AuditLog)
		_, _ = spool.ReplayPending(rt, rt.Config.BackendUnix, traceW, auditW, rt.Config.SpoolSealKeyHex)
		_ = traceW.Flush()
	}

	srv, err := proxy.NewServer(rt, "serve")
	if err != nil {
		fmt.Fprintf(os.Stderr, "server: %v\n", err)
		return 1
	}

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigCh
		_ = srv.FlushTrace()
		os.Exit(0)
	}()

	config.InstallSIGHUPHandler(rt, *cfgPath, rt.Config.ProfilesDir, rt.Config.KeyringPath)
	if err := srv.Serve(); err != nil {
		fmt.Fprintf(os.Stderr, "serve: %v\n", err)
		return 1
	}
	return 0
}

func runRecover(args []string) int {
	fs := flag.NewFlagSet("recover", flag.ExitOnError)
	backend := fs.String("backend-unix", "", "")
	cfgPath := fs.String("config", "config/proxy.json", "")
	profiles := fs.String("profiles", "", "")
	keyringPath := fs.String("keyring", "", "")
	stateDir := fs.String("state-dir", "", "")
	auditLog := fs.String("audit-log", "", "")
	tracePath := fs.String("trace", "/output/request-trace.json", "")
	_ = fs.Parse(args)

	rt, err := loadRuntime(*cfgPath, *profiles, *keyringPath, *stateDir, *auditLog, *tracePath, "", *backend, "")
	if err != nil {
		fmt.Fprintf(os.Stderr, "init: %v\n", err)
		return 1
	}

	traceW := trace.NewWriter(rt.Config.TracePath, "recover", rt.Catalog.CatalogDigest)
	auditW := audit.NewSnapshotWriter(rt.Config.AuditLog)
	_, err = spool.ReplayPending(rt, rt.Config.BackendUnix, traceW, auditW, rt.Config.SpoolSealKeyHex)
	if err != nil {
		fmt.Fprintf(os.Stderr, "recover: %v\n", err)
		return 1
	}
	if err := traceW.Flush(); err != nil {
		fmt.Fprintf(os.Stderr, "trace: %v\n", err)
		return 1
	}
	return 0
}

func loadRuntime(cfgPath, profiles, keyringPath, stateDir, auditLog, tracePath, listen, backend, ready string) (*config.Runtime, error) {
	cfg, err := config.Load(cfgPath)
	if err != nil {
		return nil, err
	}
	cfg.MergeFlags(listen, backend, stateDir, auditLog, tracePath, profiles, keyringPath, ready)
	cat, err := config.LoadProfileCatalog(cfg.ProfilesDir)
	if err != nil {
		return nil, err
	}
	kr, err := keyring.Load(cfg.KeyringPath)
	if err != nil {
		return nil, err
	}
	return &config.Runtime{
		Config:  cfg,
		Catalog: cat,
		Keyring: kr,
		Cache:   keyring.NewAuthorityCache(),
	}, nil
}
