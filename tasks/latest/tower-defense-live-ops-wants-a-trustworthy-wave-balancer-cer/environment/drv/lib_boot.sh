#!/usr/bin/env bash
# Shared path defaults for the wave tool CLI.

boot_paths() {
  ENV_ROOT="${ENV_ROOT:-/app/environment}"
  OUT_ROOT="${OUT_ROOT:-/app/output}"
  WORK_ROOT="${WORK_ROOT:-/tmp/wfc-work}"
}
