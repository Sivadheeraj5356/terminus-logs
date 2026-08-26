package config

import (
	"os"
	"strconv"
	"strings"
)

// Get returns env or default.
func Get(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

// GetInt returns integer env or default.
func GetInt(key string, def int) int {
	v := os.Getenv(key)
	if v == "" {
		return def
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return def
	}
	return n
}

// GetBool parses truthy env values.
func GetBool(key string, def bool) bool {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return def
	}
	switch strings.ToLower(v) {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		return def
	}
}

// GetCSV splits a comma-separated env var.
func GetCSV(key string, def []string) []string {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return append([]string{}, def...)
	}
	parts := strings.Split(v, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			out = append(out, p)
		}
	}
	if len(out) == 0 {
		return append([]string{}, def...)
	}
	return out
}

// RuntimeRoot resolves the application root.
func RuntimeRoot() string {
	if v := os.Getenv("RUNTIME_ROOT"); v != "" {
		return v
	}
	if v := os.Getenv("TB3_APP_ROOT"); v != "" {
		return v
	}
	return "/app"
}
