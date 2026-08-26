#!/bin/bash
set -euo pipefail

export PATH="/usr/local/cargo/bin:$PATH"
export CARGO_NET_OFFLINE=true
export CARGO_BUILD_JOBS=1

APP_ROOT="/app"
DIST="$APP_ROOT/dist"
MATRIX="$APP_ROOT/config/release_matrix.csv"
BIN="$APP_ROOT/target/release/releasekit"
WORKSPACE_TOML="$APP_ROOT/Cargo.toml"

sha_file() { sha256sum "$1" | awk '{print $1}'; }
json_bool() { if [ "$1" = "true" ]; then printf 'true'; else printf 'false'; fi; }
json_number() { grep -o '"'$1'": *[0-9]*' "$2" | head -n 1 | sed 's/.*: *//'; }
json_escape() {
  local value=$1
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  value=${value//$'\b'/\\b}
  value=${value//$'\f'/\\f}
  value=${value//$'\n'/\\n}
  value=${value//$'\r'/\\r}
  value=${value//$'\t'/\\t}
  printf '%s' "$value"
}

workspace_field() {
  local key="$1"
  awk -v key="$key" '
    /^\[workspace\.package\]/ { in_section=1; next }
    /^\[/ && $0 !~ /^\[workspace\.package\]/ { if (in_section) exit }
    in_section && $0 ~ "^[[:space:]]*" key "[[:space:]]*=" {
      sub(/^[^=]*=[[:space:]]*/, "")
      gsub(/^\"|\"$/, "")
      print
      exit
    }
  ' "$WORKSPACE_TOML"
}

package_field() {
  local manifest="$1" key="$2" value=""
  value=$(awk -v key="$key" '
    /^\[package\]/ { in_section=1; next }
    /^\[/ && $0 !~ /^\[package\]/ { if (in_section) exit }
    in_section && $0 ~ "^[[:space:]]*" key "\\.workspace[[:space:]]*=[[:space:]]*true" { print "__workspace__"; exit }
    in_section && $0 ~ "^[[:space:]]*" key "[[:space:]]*=" {
      sub(/^[^=]*=[[:space:]]*/, "")
      gsub(/^\"|\"$/, "")
      print
      exit
    }
  ' "$manifest")
  if [ "$value" = "__workspace__" ]; then
    workspace_field "$key"
  else
    printf '%s' "$value"
  fi
}

workspace_members() {
  awk '
    /^\[workspace\]/ { in_section=1; next }
    /^\[/ && $0 !~ /^\[workspace\]/ { if (in_section) exit }
    in_section && $0 ~ /"crates\// { print }
  ' "$WORKSPACE_TOML" | sed -n 's/.*"\([^"]*\)".*/\1/p'
}

crate_dependencies_json() {
  local manifest="$1" first=1 dep
  printf '['
  while IFS= read -r dep; do
    [ -n "$dep" ] || continue
    if [ "$first" -eq 0 ]; then printf ','; fi
    printf '"%s"' "$(json_escape "$dep")"
    first=0
  done < <(awk '
    /^\[dependencies\]/ { in_section=1; next }
    /^\[/ && $0 !~ /^\[dependencies\]/ { if (in_section) exit }
    in_section && $0 ~ /^[[:space:]]*[A-Za-z0-9_-]+[[:space:]]*=/ && $0 ~ /path[[:space:]]*=/ {
      sub(/^[[:space:]]*/, "")
      sub(/[[:space:]]*=.*/, "")
      print
    }
  ' "$manifest")
  printf ']'
}

workspace_json() {
  local first=1 member manifest name version license deps
  printf '['
  while IFS= read -r member; do
    [ -n "$member" ] || continue
    manifest="$APP_ROOT/$member/Cargo.toml"
    name=$(package_field "$manifest" name)
    version=$(package_field "$manifest" version)
    license=$(package_field "$manifest" license)
    deps=$(crate_dependencies_json "$manifest")
    if [ "$first" -eq 0 ]; then printf ','; fi
    printf '{"name":"%s","version":"%s","license":"%s","dependencies":%s}' \
      "$(json_escape "$name")" "$(json_escape "$version")" "$(json_escape "$license")" "$deps"
    first=0
  done < <(workspace_members)
  printf ']'
}

json_policy() {
  printf '{"profile":"%s","channel":"%s","target":"%s","feature_set":"%s","max_runtime_kb":%s,"allow_dev":%s,"blocked_license":"%s"}\n' \
    "$(json_escape "$1")" "$(json_escape "$2")" "$(json_escape "$3")" \
    "$(json_escape "$4")" "$5" "$(json_bool "$6")" "$(json_escape "$7")" > "$8"
}

write_smoke() {
  local profile="$1" out="$2"
  cat > "$out" <<SH
#!/bin/sh
set -eu
ROOT=\$(CDPATH= cd -- "\$(dirname -- "\$0")/.." && pwd)
OUT="\${1:-\$ROOT/audit-$profile.json}"
"\$ROOT/bin/releasekit" audit --profile "$profile" --matrix "\$ROOT/share/release_matrix.csv" --components "\$ROOT/share/components.csv" --locks "\$ROOT/share/locks.csv" --edges "\$ROOT/share/dependencies.csv" --out "\$OUT"
SH
  chmod 0755 "$out"
}

filter_components() {
  awk -F, -v profile="$1" 'NR==FNR { if (NR > 1 && $1 == profile) keep[$2]=1; next } FNR==1 || keep[$1]' \
    "$APP_ROOT/config/locks.csv" "$APP_ROOT/config/components.csv" > "$2"
}
filter_locks() { awk -F, -v profile="$1" 'NR==1 || $1 == profile' "$APP_ROOT/config/locks.csv" > "$2"; }
filter_edges() { awk -F, -v profile="$1" 'NR==1 || $1 == "*" || $1 == profile' "$APP_ROOT/config/dependency_edges.csv" > "$2"; }
write_licenses() { "$BIN" license-lines --components "$1" > "$2"; }

PACKAGE_NAME=$(package_field "$APP_ROOT/crates/releasekit-cli/Cargo.toml" name)
VERSION=$(package_field "$APP_ROOT/crates/releasekit-cli/Cargo.toml" version)
TARGET_TRIPLE=$(rustc -vV | awk '/^host:/ { print $2 }')
WORKSPACE_JSON=$(workspace_json)

rm -rf "$DIST"
mkdir -p "$DIST/bundles"
cd "$APP_ROOT"
cargo build --release --locked --offline -j 1 --bin releasekit

entries="$DIST/.bundle_entries"
: > "$entries"
first=1
while IFS= read -r -d '' profile \
  && IFS= read -r -d '' channel \
  && IFS= read -r -d '' target \
  && IFS= read -r -d '' feature_set \
  && IFS= read -r -d '' max_runtime \
  && IFS= read -r -d '' allow_dev \
  && IFS= read -r -d '' blocked_license; do
  bundle_name="releasekit-$profile"
  bundle_dir="$DIST/bundles/$bundle_name"
  mkdir -p "$bundle_dir/bin" "$bundle_dir/share/smoke_specs"
  cp "$BIN" "$bundle_dir/bin/releasekit"
  cp "$MATRIX" "$bundle_dir/share/release_matrix.csv"
  filter_components "$profile" "$bundle_dir/share/components.csv"
  filter_locks "$profile" "$bundle_dir/share/locks.csv"
  filter_edges "$profile" "$bundle_dir/share/dependencies.csv"
  cp "$APP_ROOT/data/smoke_specs/$profile.csv" "$bundle_dir/share/smoke_specs/$profile.csv"
  json_policy "$profile" "$channel" "$target" "$feature_set" "$max_runtime" "$allow_dev" "$blocked_license" "$bundle_dir/share/policy.json"
  write_smoke "$profile" "$bundle_dir/share/run-smoke.sh"
  sh "$bundle_dir/share/run-smoke.sh" "$bundle_dir/share/audit-preview.json"
  write_licenses "$bundle_dir/share/components.csv" "$bundle_dir/LICENSES.txt"
  printf '%s\n' "$VERSION" > "$bundle_dir/VERSION"
  find "$bundle_dir" -type d -exec chmod 0755 {} +
  find "$bundle_dir" -type f -exec chmod 0644 {} +
  chmod 0755 "$bundle_dir/bin/releasekit" "$bundle_dir/share/run-smoke.sh"
  archive="releasekit-$profile-linux-x86_64.tar.gz"
  (cd "$DIST/bundles" && tar --sort=name --mtime='UTC 2026-01-01' --owner=0 --group=0 --numeric-owner -cf - "$bundle_name" | gzip -n > "$DIST/$archive")
  preview="$bundle_dir/share/audit-preview.json"
  entry="{\"profile\":\"$(json_escape "$profile")\",\"channel\":\"$(json_escape "$channel")\",\"target\":\"$(json_escape "$target")\",\"archive\":\"$(json_escape "$archive")\",\"archive_sha256\":\"$(sha_file "$DIST/$archive")\",\"binary_sha256\":\"$(sha_file "$bundle_dir/bin/releasekit")\",\"policy_sha256\":\"$(sha_file "$bundle_dir/share/policy.json")\",\"audit_preview_sha256\":\"$(sha_file "$preview")\",\"component_count\":$(json_number component_count "$preview"),\"runtime_kb\":$(json_number runtime_kb "$preview"),\"edge_count\":$(json_number edge_count "$preview"),\"risk_score\":$(json_number risk_score "$preview")}" 
  if [ "$first" -eq 1 ]; then printf '%s' "$entry" > "$entries"; first=0; else printf ',%s' "$entry" >> "$entries"; fi
done < <("$BIN" matrix-rows --matrix "$MATRIX")

cat > "$DIST/release-manifest.json" <<JSON
{"format_version":1,"package":{"name":"$(json_escape "$PACKAGE_NAME")","version":"$(json_escape "$VERSION")","target":"$(json_escape "$TARGET_TRIPLE")"},"workspace":$WORKSPACE_JSON,"bundles":[$(cat "$entries")]}
JSON
rm -f "$entries"
(cd "$DIST" && find . -type f ! -name checksums.sha256 -print | sort | while read -r path; do sha256sum "${path#./}"; done) > "$DIST/checksums.sha256"
