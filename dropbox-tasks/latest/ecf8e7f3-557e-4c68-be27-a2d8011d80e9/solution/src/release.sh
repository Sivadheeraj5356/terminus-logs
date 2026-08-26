#!/bin/bash
set -euo pipefail
ROOT=/app; DIST=$ROOT/dist
export CARGO_NET_OFFLINE=true SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1700000000}"

# Must not read /tests (verifier isolation); a comment stating that is fine.
# Validate pnpm override migration — do not rewrite override pins / .npmrc / lockfile.
python3 <<'PY'
from pathlib import Path
import json, hashlib, gzip, re, csv
root = Path('/app')
pins = {
    'fmt': ('10.2.1', '16de8120e52729f6199371abe65cf9be293fd1461d73727bb187934db6e43313'),
    'zlib': ('1.3.1', 'f5639a1dc21583311e433c27c086f6009700df2c60ef12a7362d830be5f63907'),
    'spdlog': ('1.13.0', 'a6796ab08339bdb8a7b9be12d9baec92f38cb58434ea3f1ad3f1df991dfc0f4d'),
}

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

for name, (ver, digest) in pins.items():
    data = json.loads((root/'overrides'/'deps'/f'{name}.json').read_text(encoding='utf-8'))
    assert data['name'] == name
    assert data['provide'] == name
    assert data['version'] == ver
    assert data['resolved'] == f'file:///app/pnpm-store/{name}-{ver}.tgz'
    assert data['integrity'].lower() == f'sha256:{digest}'
    text = json.dumps(data)
    assert 'https://' not in text
    assert 'registry.npmjs.org' not in text
    archive = root / 'pnpm-store' / f'{name}-{ver}.tgz'
    assert archive.is_file() and archive.stat().st_size > 32
    assert sha256_file(archive) == digest
    with gzip.open(archive, 'rb') as gz:
        gz.read(1)

npmrc = (root/'.npmrc').read_text(encoding='utf-8')
assert re.search(r'(?m)^\s*offline\s*=\s*true\s*$', npmrc)
assert re.search(r'(?m)^\s*store-dir\s*=\s*/app/pnpm-store\s*$', npmrc)
assert (root/'legacy-pnpm-notes.txt').read_text(encoding='utf-8').strip() == '# emptied for pnpm'

pkg = json.loads((root/'package.json').read_text(encoding='utf-8'))
ov = pkg['pnpm']['overrides']
for name, (ver, _) in pins.items():
    assert ov[name] == f'file:///app/pnpm-store/{name}-{ver}.tgz'
lock = (root/'pnpm-lock.yaml').read_text(encoding='utf-8')
for name, (ver, digest) in pins.items():
    assert f'file:///app/pnpm-store/{name}-{ver}.tgz' in lock
    assert f'sha256:{digest}' in lock
    assert 'registry.npmjs.org' not in lock
ws = (root/'pnpm-workspace.yaml').read_text(encoding='utf-8')
assert "'.'" in ws or '"."' in ws or "- ." in ws

for row in csv.DictReader((root/'config'/'deps.csv').open(encoding='utf-8')):
    coord = row['coordinate']
    if coord in {'dep:fmt', 'dep:zlib', 'dep:spdlog', 'dep:legacy', 'dep:jsonA', 'dep:jsonB'}:
        assert not (row.get('patch_url') or '').strip(), f'patch_url must be empty for {row["lane"]}:{coord}'
    if coord in {'dep:fmt', 'dep:zlib', 'dep:spdlog'}:
        basename = coord.split(':', 1)[1]
        assert row['provide'] == basename, f"{row['lane']}:{coord} provide must be {basename}"
        assert not row['version'].startswith('v')
        assert row['source_url'].startswith('file:///app/pnpm-store/')
        assert row['source_hash'].startswith('sha256:')
print('pnpm migration validated')
PY

rm -rf "$DIST"; mkdir -p "$DIST/bundles"

python3 <<'PY'
from pathlib import Path
import json, hashlib, gzip
root = Path('/app')

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

def mirror_ok(url: str, source_hash: str) -> bool:
    if not url.startswith('file:///app/pnpm-store/'):
        return False
    path = Path(url[len('file://'):])
    if not path.is_file() or path.stat().st_size <= 32:
        return False
    try:
        with gzip.open(path, 'rb') as gz:
            gz.read(1)
    except OSError:
        return False
    expect = source_hash[7:] if source_hash.startswith('sha256:') else source_hash
    return sha256_file(path) == expect.lower()

deps = []
for p in sorted((root / 'overrides' / 'deps').glob('*.json')):
    data = json.loads(p.read_text(encoding='utf-8'))
    url = data['resolved']
    h = data['integrity']
    if not h.startswith('sha256:'):
        h = 'sha256:' + h.lower()
    else:
        h = 'sha256:' + h[7:].lower()
    deps.append({
        "name": data['name'], "provide": data['provide'], "version": data['version'],
        "source_url": url, "source_hash": h, "mirror_ok": mirror_ok(url, h),
    })
legacy = root / 'legacy-pnpm-notes.txt'
cleared = (not legacy.exists()) or legacy.read_text().strip() in {'# emptied for pnpm', ''}
npmrc = (root / '.npmrc').read_text(encoding='utf-8')
offline = any(ln.strip() == 'offline=true' for ln in npmrc.splitlines())
report = {
    "format_version": 1,
    "deps": deps,
    "legacy_cleared": bool(cleared),
    "offline_pnpm_mode": bool(offline),
    "cargo_packages": [
        __import__('tomllib').loads(p.read_text())['package']['name']
        for p in sorted((root/'crates').glob('*/Cargo.toml'))
    ],
}
(root / 'dist' / 'pnpm-report.json').write_text(json.dumps(report, indent=2) + '\n')
PY

cargo build --release --locked --offline -p pnpmfix-cli
BIN=$ROOT/target/release/pnpmfix; test -x "$BIN"
LIC=$(mktemp); { for f in $(ls "$ROOT/licenses"|sort); do cat "$ROOT/licenses/$f"; echo; done; } > "$LIC"
filter_csv(){ python3 - "$1" "$2" "$3" "$4" <<'PY'
import sys
src,dest,col,want=sys.argv[1:5]; col=int(col)
lines=open(src,encoding='utf-8').read().splitlines(); header=lines[0]
rows=[ln for ln in lines[1:] if ln and ln.split(',')[col]==want]
if rows: open(dest,'w',encoding='utf-8').write(header+'\n'+'\n'.join(rows)+'\n')
PY
}
bundle_entries='[]'
while IFS=, read -r lane retention_hops; do
  [[ "$lane" == "lane" ]] && continue
  bundle=$DIST/bundles/pnpmfix-$lane
  mkdir -p "$bundle/bin" "$bundle/share"
  cp "$BIN" "$bundle/bin/pnpmfix"; chmod 0755 "$bundle/bin/pnpmfix"
  cp "$LIC" "$bundle/LICENSES.txt"; printf 'pnpmfix 0.8.6\n' > "$bundle/VERSION"
  python3 -c "import json;from pathlib import Path;Path(r'$bundle/share/lane-policy.json').write_text(json.dumps({'lane':'$lane','retention_hops':int('$retention_hops')},indent=2)+'\n')"
  filter_csv "$ROOT/data/graphs/edges.csv" "$bundle/share/edges.csv" 0 "$lane" || true
  filter_csv "$ROOT/data/graphs/artifacts.csv" "$bundle/share/artifacts.csv" 0 "$lane" || true
  filter_csv "$ROOT/config/deps.csv" "$bundle/share/deps.csv" 0 "$lane" || true
  filter_csv "$ROOT/config/xor.csv" "$bundle/share/xor.csv" 0 "$lane" || true
  cp "$ROOT/config/mirrors.csv" "$bundle/share/mirrors.csv"
  cp "$ROOT/config/pins.csv" "$bundle/share/pins.csv"
  cp "$ROOT/config/bans.csv" "$bundle/share/bans.csv"
  cp "$ROOT/config/forbidden-hosts.csv" "$bundle/share/forbidden-hosts.csv"
  [[ -f $bundle/share/edges.csv ]] || printf 'lane,parent,child,edge_kind\n' > "$bundle/share/edges.csv"
  [[ -f $bundle/share/artifacts.csv ]] || printf 'lane,coordinate\n' > "$bundle/share/artifacts.csv"
  [[ -f $bundle/share/deps.csv ]] || printf 'lane,coordinate,provide,version,source_url,source_hash,patch_url\n' > "$bundle/share/deps.csv"
  [[ -f $bundle/share/xor.csv ]] || printf 'lane,group,provide\n' > "$bundle/share/xor.csv"
  cat > "$bundle/share/run-smoke.sh" <<SMOKE
#!/bin/sh
set -eu
HERE=\$(CDPATH= cd -- "\$(dirname "\$0")/.." && pwd)
OUT=\${1:-\$HERE/share/inspect-preview.json}
POL=\$HERE/share/lane-policy.json
LANE=\$(python3 -c "import json;print(json.load(open(\"\$POL\"))['lane'])")
HOPS=\$(python3 -c "import json;print(json.load(open(\"\$POL\"))['retention_hops'])")
"\$HERE/bin/pnpmfix" inspect --lane "\$LANE" --edges "\$HERE/share/edges.csv" --artifacts "\$HERE/share/artifacts.csv" \\
  --deps "\$HERE/share/deps.csv" --mirrors "\$HERE/share/mirrors.csv" --pins "\$HERE/share/pins.csv" \\
  --xor "\$HERE/share/xor.csv" --bans "\$HERE/share/bans.csv" --forbidden-hosts "\$HERE/share/forbidden-hosts.csv" \\
  --retention-hops "\$HOPS" --out "\$OUT"
SMOKE
  chmod 0755 "$bundle/share/run-smoke.sh"
  "$bundle/share/run-smoke.sh" "$bundle/share/inspect-preview.json"
  archive=$DIST/pnpmfix-$lane-linux-x86_64.tar.gz
  ( cd "$DIST/bundles"; find "pnpmfix-$lane" -print0 | LC_ALL=C sort -z | tar --null -T - --mtime="@${SOURCE_DATE_EPOCH}" --owner=0 --group=0 --numeric-owner -cf - | gzip -n > "$archive" )
  entry=$(python3 - "$lane" "$archive" "$bundle" <<'PY'
import json,hashlib,sys
from pathlib import Path
lane,archive,bundle=sys.argv[1:4]; bundle=Path(bundle)
def sha(p):
  h=hashlib.sha256()
  with open(p,'rb') as f:
    for c in iter(lambda:f.read(1<<20),b''): h.update(c)
  return h.hexdigest()
prev=json.loads((bundle/'share'/'inspect-preview.json').read_text())
print(json.dumps({"lane":lane,"archive":Path(archive).name,"archive_sha256":sha(archive),
 "binary_sha256":sha(bundle/'bin'/'pnpmfix'),"policy_sha256":sha(bundle/'share'/'lane-policy.json'),
 "inspect_preview_sha256":sha(bundle/'share'/'inspect-preview.json'),
 "artifact_count":len(prev['artifacts']),"hold_count":prev['totals']['hold'],
 "risk_score_total":prev['totals']['risk_score_total']}))
PY
)
  bundle_entries=$(python3 -c "import json,sys;a=json.loads(sys.argv[1]);a.append(json.loads(sys.argv[2]));print(json.dumps(a))" "$bundle_entries" "$entry")
done < "$ROOT/config/release_matrix.csv"

python3 - "$bundle_entries" <<'PY'
import json,tomllib,sys
from pathlib import Path
bundles=json.loads(sys.argv[1]); root=Path('/app')
ws=tomllib.loads((root/'Cargo.toml').read_text())
wlicense=ws['workspace']['package']['license']; wversion=ws['workspace']['package']['version']
workspace=[]
# Path order: sorted(crates/*/Cargo.toml) — directory basename may differ from package name.
for p in sorted((root/'crates').glob('*/Cargo.toml')):
  data=tomllib.loads(p.read_text()); pkg=data['package']
  lic=pkg.get('license',wlicense); ver=pkg.get('version',wversion)
  if isinstance(lic,dict) and lic.get('workspace'): lic=wlicense
  if isinstance(ver,dict) and ver.get('workspace'): ver=wversion
  workspace.append({'name':pkg['name'],'version':ver,'license':lic,'dependencies':sorted((data.get('dependencies') or {}).keys())})
fetch=json.loads((root/'dist'/'pnpm-report.json').read_text())
manifest={'format_version':1,'package':{'name':'pnpmfix-cli','version':'0.8.6','target':'x86_64-unknown-linux-gnu'},
 'workspace':workspace,'fetch':fetch,'bundles':bundles}
(root/'dist'/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
PY
( cd "$DIST"; find . -type f ! -name checksums.sha256 -printf '%P\n' | LC_ALL=C sort | while read -r rel; do echo "$(sha256sum "$rel"|awk '{print $1}')  $rel"; done > checksums.sha256 )
