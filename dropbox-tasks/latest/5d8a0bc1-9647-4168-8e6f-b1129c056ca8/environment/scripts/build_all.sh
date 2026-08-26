#!/bin/bash
set -euo pipefail
ROOT="/app/environment"
cd "${ROOT}"

mvn -q -DskipTests package

mkdir -p "${ROOT}/cmd/classes" "${ROOT}/bin"
# Compile daemon + checker against module jars (no Maven module for cmd/).
CP="$(echo "${ROOT}"/lib_a/target/*.jar "${ROOT}"/lib_b/target/*.jar "${ROOT}"/lib_c/target/*.jar | tr ' ' ':')"
javac --release 21 -cp "${CP}" -d "${ROOT}/cmd/classes" \
  "${ROOT}/cmd/og_daemon/Run.java" \
  "${ROOT}/cmd/og_daemon/Main.java" \
  "${ROOT}/cmd/og_check/Engine.java" \
  "${ROOT}/cmd/og_check/Main.java"

FULL_CP="${CP}:${ROOT}/cmd/classes"
cat > "${ROOT}/bin/og_check" <<EOF
#!/bin/bash
exec java -Dovg.cp="${FULL_CP}" -cp "${FULL_CP}" org.ovg.check.Main "\$@"
EOF
chmod +x "${ROOT}/bin/og_check" "${ROOT}/scripts/"*.sh "${ROOT}/migrations/"*.sh

# Stash classpath for drive_grid
echo "${FULL_CP}" > "${ROOT}/bin/classpath.txt"
echo "build_ok"
