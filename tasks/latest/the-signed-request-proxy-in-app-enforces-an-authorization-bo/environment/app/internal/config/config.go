package config

import (
	"encoding/json"
	"fmt"
	"os"
)

type ProxyConfig struct {
	ListenUnix       string `json:"listen_unix"`
	BackendUnix      string `json:"backend_unix"`
	StateDir         string `json:"state_dir"`
	SpoolDir         string `json:"spool_dir"`
	AuditLog         string `json:"audit_log"`
	TracePath        string `json:"trace_path"`
	ProfilesDir      string `json:"profiles_dir"`
	KeyringPath      string `json:"keyring_path"`
	DefaultProfile   string `json:"default_profile"`
	BodyLimit        int    `json:"body_limit"`
	ReplayOnStart    bool   `json:"replay_on_start"`
	ReadyFile        string `json:"ready_file"`
	SpoolSealKeyHex  string `json:"spool_seal_key_hex"`
}

func Load(path string) (*ProxyConfig, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read config: %w", err)
	}
	var cfg ProxyConfig
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("parse config: %w", err)
	}
	if cfg.BodyLimit <= 0 {
		cfg.BodyLimit = 1048576
	}
	if cfg.SpoolDir == "" {
		cfg.SpoolDir = cfg.StateDir + "/spool"
	}
	return &cfg, nil
}

func (c *ProxyConfig) MergeFlags(listen, backend, state, audit, trace, profiles, keyring, ready string) {
	if listen != "" {
		c.ListenUnix = listen
	}
	if backend != "" {
		c.BackendUnix = backend
	}
	if state != "" {
		c.StateDir = state
		c.SpoolDir = state + "/spool"
	}
	if audit != "" {
		c.AuditLog = audit
	}
	if trace != "" {
		c.TracePath = trace
	}
	if profiles != "" {
		c.ProfilesDir = profiles
	}
	if keyring != "" {
		c.KeyringPath = keyring
	}
	if ready != "" {
		c.ReadyFile = ready
	}
}
