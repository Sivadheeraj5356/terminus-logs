#!/usr/bin/env bash
# Runtime defaults exported before pack replay.
# shellcheck disable=SC2034
PAM_HONOR_OVERRIDE="${PAM_HONOR_OVERRIDE:-1}"
PAM_PROBE_IMPLIES_LOCK="${PAM_PROBE_IMPLIES_LOCK:-1}"
PAM_REALM_FOLD="${PAM_REALM_FOLD:-preserve}"
PAM_BIND_DIGEST="${PAM_BIND_DIGEST:-0}"
