#!/bin/bash
set -euo pipefail

config="${MODEL_SOURCE_CONFIG:-/app/config/model-source.properties}"
dest="${MODEL_DIR:-/app/models/mobilenet-v3-parity}"
repository="$(sed -n 's/^repository=//p' "$config")"
revision="$(sed -n 's/^revision=//p' "$config")"
test -n "$repository" && test -n "$revision"
mkdir -p "$dest"

for file in mobilenet_v3_large.pt mobilenet_v3_large.onnx mobilenet_v3_large.onnx.data config.json; do
  expected="$(sed -n "s/^${file//./\\.}=//p" "$config")"
  test "${#expected}" -eq 64
  if [ -f "$dest/$file" ] && echo "$expected  $dest/$file" | sha256sum -c --status; then
    continue
  fi
  tmp="$(mktemp "$dest/.${file}.XXXXXX")"
  trap 'rm -f "$tmp"' EXIT
  curl -fL --retry 3 --connect-timeout 20 \
    "https://huggingface.co/$repository/resolve/$revision/$file" -o "$tmp"
  echo "$expected  $tmp" | sha256sum -c --status
  mv -f "$tmp" "$dest/$file"
  trap - EXIT
done
