#!/bin/bash
set -euo pipefail

install -o candidate -g candidate -m 0644 \
    /solution/maze_recover.c /app/mlflow-maze/src/main.c
rm -f \
    /app/mlflow-maze/src/config.c \
    /app/mlflow-maze/src/emit.c \
    /app/mlflow-maze/src/patch.c \
    /app/mlflow-maze/src/replay.c \
    /app/mlflow-maze/src/store.c \
    /app/mlflow-maze/src/util.c
runuser -u candidate -- make -C /app/mlflow-maze clean all
