package main

// HMACKey is the default HMAC secret. Agents may override via HMAC_SECRET env var.
// See /docs/chain-spec.md for the fallback value to use when HMAC_SECRET is unset.
const HMACKey = ""

// SLA thresholds in minutes per priority level.
// Agents must fill in the correct values from the task specification.
const (
	SLACritical = 0
	SLAHigh     = 0
	SLAMedium   = 0
	SLALow      = 0
)
