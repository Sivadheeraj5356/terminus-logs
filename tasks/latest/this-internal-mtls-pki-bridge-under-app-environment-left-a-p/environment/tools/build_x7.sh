#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -d /app/environment/n3 ]; then
  ROOT=/app/environment
fi
OUT="${ROOT}/classes"
rm -rf "${OUT}"
mkdir -p "${OUT}"
mapfile -t SOURCES < <(find "${ROOT}/n3" "${ROOT}/m8" "${ROOT}/t5" "${ROOT}/driver" -name '*.java' | sort)
javac -encoding UTF-8 -d "${OUT}" "${SOURCES[@]}"
mkdir -p "${ROOT}/bin" /app/bin
cat > "${ROOT}/bin/x7" <<EOF
#!/bin/bash
exec java -cp "${OUT}" drv.Main "\$@"
EOF
chmod +x "${ROOT}/bin/x7"
cp "${ROOT}/bin/x7" /app/bin/x7
chmod +x /app/bin/x7
