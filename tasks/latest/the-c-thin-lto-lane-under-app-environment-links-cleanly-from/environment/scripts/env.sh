#!/bin/bash
export APP_ROOT=/app/environment
export WORK_ROOT=/app/work
export BUILD_ROOT="${WORK_ROOT}/build"
export GEN_ROOT="${WORK_ROOT}/gen"
export LTO_ROOT="${WORK_ROOT}/lto"
export OBJ_ROOT="${WORK_ROOT}/obj"
export BIN_ROOT="${WORK_ROOT}/bin"
export PROFILE="${PROFILE:-release}"
export OBSERVATION_OUT=/app/output/lto_observation.json
