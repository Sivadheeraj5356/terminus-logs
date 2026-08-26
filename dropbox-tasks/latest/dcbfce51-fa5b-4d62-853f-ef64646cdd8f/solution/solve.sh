#!/usr/bin/env bash
set -euo pipefail
export TZ=UTC

cd "$(dirname "$0")"

# Idempotent patch apply: skip when reverse dry-run shows already applied.
if ! patch -p1 -d / --reverse --dry-run --force < patches/cfaxis-calaxis-member_plan.py.patch >/dev/null 2>&1; then
  patch -p1 -d / --forward --reject-file=- < patches/cfaxis-calaxis-member_plan.py.patch
fi
if ! patch -p1 -d / --reverse --dry-run --force < patches/cfaxis-calaxis-calendar_merge.py.patch >/dev/null 2>&1; then
  patch -p1 -d / --forward --reject-file=- < patches/cfaxis-calaxis-calendar_merge.py.patch
fi
if ! patch -p1 -d / --reverse --dry-run --force < patches/cfaxis-calaxis-axis_run.py.patch >/dev/null 2>&1; then
  patch -p1 -d / --forward --reject-file=- < patches/cfaxis-calaxis-axis_run.py.patch
fi
if ! patch -p1 -d / --reverse --dry-run --force < patches/cfaxis-calaxis-axis_report.py.patch >/dev/null 2>&1; then
  patch -p1 -d / --forward --reject-file=- < patches/cfaxis-calaxis-axis_report.py.patch
fi

test -x /usr/local/bin/climconvert
mkdir -p /app/bin
ln -sfn /usr/local/bin/climconvert /app/bin/climconvert
python3 -c 'import cfaxis; import cfaxis.calaxis'
/app/bin/climconvert --help >/dev/null

rm -rf /var/lib/climconvert/cache/*
mkdir -p /output

/app/bin/climconvert compact --manifest /app/data/climate-axis-manifest.toml

python3 - <<'PY'
import json
from pathlib import Path
report = json.loads(Path("/output/climate-axis-report.json").read_text())
assert report["report_format_version"] == 1
assert report["conflict"] is False
assert report["observation_count"] >= 5
assert Path("/output/archive.ccf").exists()
assert Path("/output/archive-monthly.ccf").exists()
assert report["archive_digest"] == __import__("hashlib").sha256(Path("/output/archive.ccf").read_bytes()).hexdigest()
print("oracle climate-axis ok", report["observation_count"])
PY

work=$(mktemp -d)
/app/bin/climconvert convert --in /data/samples/gregorian_monthly.ccf --out "$work/g.cft"
/app/bin/climconvert convert --in "$work/g.cft" --out "$work/g.ccf"
/app/bin/climconvert validate --in /data/samples/gregorian_monthly.ccf
rm -rf "$work"
