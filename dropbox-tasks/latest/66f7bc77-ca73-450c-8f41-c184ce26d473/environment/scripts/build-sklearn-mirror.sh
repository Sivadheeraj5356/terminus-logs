#!/bin/bash
set -euo pipefail

MIRROR="/app/mirrors/scikit-learn.git"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

cd "$WORKDIR"
git init -q
git config user.email "build@atlasbatch.internal"
git config user.name "AtlasBatch Build"
git commit --allow-empty -q -m "mirror root"

for tag in 1.3.2 1.4.2 1.5.0; do
    git tag "$tag"
done

rm -rf "$MIRROR"
git clone --bare . "$MIRROR"
