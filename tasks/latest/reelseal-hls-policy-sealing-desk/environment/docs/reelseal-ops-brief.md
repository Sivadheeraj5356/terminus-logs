# ReelSeal operations brief

ReelSeal is an offline media sealing desk. Operators migrate AES-128 HLS packaging from legacy YAML/TOML into a Go pipeline that consults a Gin policy API for key identifiers and signing policy, then emits provenance-bound encryption manifests.

Desk binary: /app/bin/reelseal
Desk driver: /app/scripts/reelseal-desk.sh
Policy API default: http://127.0.0.1:8742
Engine identity string: reelseal-runtime/v1
Release tag name: reelseal-v1.0.0

Stage order is mandatory: fetch → segment → policy-bind → seal-manifest → hook-check → release-tag → package.
