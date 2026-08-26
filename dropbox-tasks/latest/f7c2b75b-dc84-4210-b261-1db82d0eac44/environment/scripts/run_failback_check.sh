#!/bin/bash
set -euo pipefail

# Operator repro for HA failback on the configured pair (see configs/pair.toml).
vivostep run --scenario wp-maint --cold "${1:-}"
vivostep run --scenario wp-maint "${1:-}"
vivostep examine --surface dual
