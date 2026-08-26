#!/usr/bin/env bash
set -euo pipefail

if [[ -d /workspace/beacon-drift-go-build-rescue ]]; then
  ROOT=/workspace/beacon-drift-go-build-rescue
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  ROOT="$(cd "$SCRIPT_DIR/../environment/workspace/beacon-drift-go-build-rescue" && pwd)"
fi

cd "$ROOT"

python3 - <<'PY'
from pathlib import Path

mod = Path("go.mod")
lines = mod.read_text(encoding="utf-8").splitlines()
if not lines or not lines[0].startswith("module "):
    raise SystemExit("go.mod does not start with a module declaration")

lines[0] = "module example.com/coastal/beacon-drift"
cleaned = []
skip_block = False
for line in lines:
    stripped = line.strip()
    if stripped.startswith("require github.com/segmentio/ksuid"):
        continue
    if stripped == "require (":
        skip_block = True
        block = [line]
        continue
    if skip_block:
        block.append(line)
        if stripped == ")":
            skip_block = False
            if any("github.com/segmentio/ksuid" not in item for item in block[1:-1]):
                cleaned.extend(item for item in block if "github.com/segmentio/ksuid" not in item)
        continue
    cleaned.append(line)

text = "\n".join(cleaned).strip() + "\n"
mod.write_text(text, encoding="utf-8")

makefile = Path("Makefile")
raw = makefile.read_text(encoding="utf-8").splitlines()

variables = [
    "PROFILE_SOURCE := config/beacon_profiles.json",
    "PROFILE_STAGE_DIR := internal/packets/config",
    "PROFILE_STAGE := $(PROFILE_STAGE_DIR)/beacon_profiles.json",
    "BINARY := bin/beacon-drift",
    "PACKAGE := ./cmd/beacon-drift",
]
helper = [
    "define run_with_profiles",
    "\t@set -eu; \\",
    "\tmkdir -p \"$(PROFILE_STAGE_DIR)\"; \\",
    "\tcp \"$(PROFILE_SOURCE)\" \"$(PROFILE_STAGE)\"; \\",
    "\ttrap 'rm -rf \"$(PROFILE_STAGE_DIR)\"' EXIT INT TERM; \\",
    "\t$(1)",
    "endef",
]
targets = {
    "test": ["\t$(call run_with_profiles,GOPROXY=off GOSUMDB=off go test ./...)"],
    "build": [
        "\t@mkdir -p \"$(dir $(BINARY))\"",
        "\t$(call run_with_profiles,GOPROXY=off GOSUMDB=off go build -trimpath -ldflags=\"-buildid=\" -o \"$(BINARY)\" \"$(PACKAGE)\")",
    ],
    "smoke": ["\t./scripts/smoke-test.sh"],
    "clean": ["\t@rm -rf bin dist coverage.out \"$(PROFILE_STAGE_DIR)\""],
}

body = []
i = 0
while i < len(raw):
    line = raw[i]
    stripped = line.strip()
    if any(line.startswith(prefix.split(" := ")[0] + " :=") for prefix in variables):
        i += 1
        continue
    if stripped == "define run_with_profiles":
        i += 1
        while i < len(raw) and raw[i].strip() != "endef":
            i += 1
        i += 1
        continue
    if stripped.endswith(":") and stripped[:-1] in targets:
        name = stripped[:-1]
        body.append(f"{name}:")
        body.extend(targets[name])
        i += 1
        while i < len(raw) and (raw[i].startswith("\t") or raw[i].strip() == ""):
            i += 1
        continue
    body.append(line)
    i += 1

while body and body[0].strip() == "":
    body.pop(0)

rebuilt = variables + [""] + helper + [""] + body
makefile.write_text("\n".join(rebuilt).rstrip() + "\n", encoding="utf-8")
PY
