#!/usr/bin/env bash
# Creator/build-time fixture generator. Uses dnssec-keygen; signing happens at publish time.
set -euo pipefail

DATA_ROOT="${DATA_ROOT:-/data}"
EPOCH=1784006400

gen_keys() {
  local ws="$1"
  local origin="${2:-example.test.}"
  local keys_dir="${ws}/keys"
  mkdir -p "${keys_dir}"
  rm -f "${keys_dir}"/K*
  (
    cd "${keys_dir}"
    dnssec-keygen -q -a RSASHA256 -b 2048 -n ZONE -K . "${origin}"
    dnssec-keygen -q -a RSASHA256 -b 2048 -n ZONE -f KSK -K . "${origin}"
    chmod -R a+r .
  )
}

write_inventory() {
  local ws="$1"
  local origin="${2:-example.test.}"
  local zsk_role="${3:-ZSK}"
  local zsk_status="${4:-active}"
  local ksk_role="${5:-KSK}"
  local ksk_status="${6:-active}"
  local keys_dir="${ws}/keys"
  local zsk="" ksk=""
  for f in "${keys_dir}"/K*.key; do
    if grep -qi "key-signing key" "${f}" 2>/dev/null; then
      ksk="${f}"
    else
      zsk="${f}"
    fi
  done
  python3 - <<'PY' "${ws}" "${origin}" "${zsk}" "${ksk}" "${zsk_role}" "${zsk_status}" "${ksk_role}" "${ksk_status}"
import json, os, re, sys, pathlib
ws, origin, zsk, ksk, zr, zs, kr, ks = sys.argv[1:]

def entry(path, role, status):
    key_path = pathlib.Path(path)
    priv_path = key_path.with_suffix('.private')
    text = key_path.read_text()
    priv = priv_path.read_text()
    flags = 256
    algo = 8
    m = re.search(r'Algorithm:\s+(\d+)', priv)
    if m:
        algo = int(m.group(1))
    m = re.search(r'Flags:\s+(\d+)', text)
    if m:
        flags = int(m.group(1))
    elif 'Publish: YES' in priv:
        flags = 257
    tag = int(key_path.name.split('+')[-1].replace('.key',''))
    pub = ''
    m = re.search(r'Public-Key:\s*\(?\s*([A-Za-z0-9+/=\s]+)\)?', priv, re.S)
    if m:
        pub = ''.join(m.group(1).split())
    else:
        chunks = re.findall(r'[A-Za-z0-9+/=]{40,}', text)
        pub = max(chunks, key=len) if chunks else ''
    if not pub:
        raise SystemExit(f'no public key in {path}')
    return {
        "id": f"key-{tag}",
        "role": role,
        "status": status,
        "algorithm": algo,
        "flags": flags,
        "public_key_b64": pub,
        "private_key_path": priv_path.name,
        "key_tag": tag,
    }

keys = []
if zsk: keys.append(entry(zsk, zr, zs))
if ksk: keys.append(entry(ksk, kr, ks))
inv = {"origin": origin, "keys": keys}
pathlib.Path(ws, 'inventory.json').write_text(json.dumps(inv, indent=2) + '\n')
PY
}

write_previous_manifest() {
  local ws="$1"
  local serial="$2"
  local prev="${ws}/previous"
  mkdir -p "${prev}"
  cp "${ws}/unsigned.zone" "${prev}/unsigned.zone"
  python3 - <<'PY' "${ws}" "${serial}" "${prev}/publication-manifest.json"
import hashlib, json, pathlib, sys
ws, serial, manifest = sys.argv[1:4]
inv = json.loads(pathlib.Path(ws,'inventory.json').read_text())
unsigned = pathlib.Path(ws,'unsigned.zone').read_bytes()
doc = {
  "schema_version": 2,
  "origin": inv["origin"],
  "epoch": 1784006400,
  "epoch_id": "fixture-prev",
  "plan_digest": "fixture",
  "zone_digest": "0"*64,
  "input_digest": hashlib.sha256(unsigned).hexdigest(),
  "serial": int(serial),
  "keys": [],
  "nsec3": {"algorithm":2,"flags":0,"iterations":0,"salt":"-"},
  "signature_start": 1784006400,
  "signature_end": 1784006400+2592000,
}
for k in inv['keys']:
    doc['keys'].append({
        'lineage_id': f"tag:{k['key_tag']}:alg:{k['algorithm']}",
        'role': k['role'], 'status': k['status'], 'key_tag': k['key_tag'],
        'algorithm': k['algorithm'], 'public_key_b64': k['public_key_b64'],
    })
pathlib.Path(manifest).write_text(json.dumps(doc, indent=2)+'\n')
PY
}

build_scenario() {
  local name="$1"
  local ws="${DATA_ROOT}/workflows/${name}"
  gen_keys "${ws}"
  case "${name}" in
    normal)
      write_inventory "${ws}" "example.test." ZSK active KSK active
      write_previous_manifest "${ws}" 2024071400
      ;;
    interrupted)
      write_inventory "${ws}" "example.test." ZSK active KSK active
      write_previous_manifest "${ws}" 2024071500
      mkdir -p "${ws}/staging/pending-epoch"
      python3 - <<'PY' "${ws}"
import json, pathlib, sys
ws = pathlib.Path(sys.argv[1])
cr = {
  'epoch_id':'pending-epoch-1','plan_digest':'interrupted-plan',
  'zone_digest':'0'*64,'manifest_digest':'0'*64,
  'serial':2024071502,
  'nsec3':{'algorithm':2,'flags':0,'iterations':0,'salt':'deadbeefdeadbeef'},
  'signature_start':1784006400,'signature_end':1784006400+2592000,
}
(ws/'staging/pending-epoch/commit-record.json').write_text(json.dumps(cr, indent=2)+'\n')
(ws/'release-log.jsonl').write_text(json.dumps({
  'sequence':1,'epoch_id':'pending-epoch-1','phase':'staged','plan_digest':'interrupted-plan',
  'serial':2024071502,'keys':[], 'nsec3':cr['nsec3'], 'timestamp':'2024-07-14T00:00:00Z',
})+'\n')
PY
      ;;
    rollback)
      local keys_dir="${ws}/keys"
      rm -f "${keys_dir}"/K*
      (cd "${keys_dir}" && dnssec-keygen -q -a RSASHA256 -b 2048 -n ZONE -f KSK -K . example.test.)
      local old_ksk
      old_ksk=$(ls "${keys_dir}"/K*.key | head -1)
      (cd "${keys_dir}" && dnssec-keygen -q -a RSASHA256 -b 2048 -n ZONE -K . example.test.)
      (cd "${keys_dir}" && dnssec-keygen -q -a RSASHA256 -b 2048 -n ZONE -f KSK -K . example.test.)
      write_inventory "${ws}" "example.test." ZSK active KSK active
      write_previous_manifest "${ws}" 2024071500
      python3 - <<'PY' "${ws}" "${old_ksk}"
import json, pathlib, re, sys
ws, old = sys.argv[1], pathlib.Path(sys.argv[2])
text = old.read_text(); priv = old.with_suffix('.private').read_text()
flags = 257; algo = 8
m = re.search(r'Algorithm:\s+(\d+)', priv)
if m: algo = int(m.group(1))
tag = int(old.name.split('+')[-1].replace('.key',''))
m = re.search(r'Public-Key:\s*\(?\s*([A-Za-z0-9+/=\s]+)\)?', priv, re.S)
if m:
    pub = ''.join(m.group(1).split())
else:
    chunks = re.findall(r'[A-Za-z0-9+/=\s]{40,}', text)
    pub = ''.join(max(chunks, key=len).split()) if chunks else ''
snap = {'schema_version':1,'origin':'example.test.','serial':2024071400,
  'keys':[{'role':'KSK','status':'active','key_tag':tag,'algorithm':algo,'flags':flags,'public_key_b64':pub}]}
pathlib.Path(ws,'operator-snapshot-v1.json').write_text(json.dumps(snap, indent=2)+'\n')
pathlib.Path(ws,'release-log.jsonl').write_text(json.dumps({
  'sequence':1,'epoch_id':'rollback-prev','phase':'accepted','plan_digest':'rollback-plan',
  'serial':2024071500,
  'keys':[{'lineage_id':f'tag:{tag}:alg:{algo}','role':'KSK','status':'retired','key_tag':tag}],
  'nsec3':{'algorithm':2,'flags':0,'iterations':0,'salt':'cafebabecafebabe'},
  'timestamp':'2024-07-14T00:00:00Z',
})+'\n')
PY
      ;;
    wrap)
      write_inventory "${ws}" "example.test." ZSK active KSK active
      write_previous_manifest "${ws}" 4294967290
      python3 - <<'PY' "${ws}"
import json, pathlib, sys
ws = pathlib.Path(sys.argv[1])
mf = json.loads((ws/'previous/publication-manifest.json').read_text())
mf['serial'] = 4294967290
(ws/'previous/publication-manifest.json').write_text(json.dumps(mf, indent=2)+'\n')
(ws/'release-log.jsonl').write_text(json.dumps({
  'sequence':1,'epoch_id':'wrap-prev','phase':'accepted','plan_digest':'wrap-plan',
  'serial':4294967290,'keys':[], 'nsec3':{'algorithm':2,'flags':0,'iterations':0,'salt':'wrapwrapwrapwrap'},
  'timestamp':'2024-07-14T00:00:00Z',
})+'\n')
PY
      ;;
    altorigin)
      cp "${DATA_ROOT}/workflows/normal/unsigned.zone" "${ws}/unsigned.zone"
      sed -i 's/example\.test\./alt.example.test./g' "${ws}/unsigned.zone"
      cat > "${ws}/publish.toml" <<'EOF'
origin = "alt.example.test."
unsigned_zone = "unsigned.zone"
inventory = "inventory.json"
journal = "release-log.jsonl"
previous_dir = "previous"
keys_dir = "keys"
signed_output_name = "alt.example.test.signed"
manifest_name = "publication-manifest.json"
signature_lifetime = 2592000
epoch = 1784006400

[nsec3]
algorithm = 2
flags = 0
iterations = 0
salt_seed = "alt-example-origin"
EOF
      : > "${ws}/release-log.jsonl"
      gen_keys "${ws}" "alt.example.test."
      write_inventory "${ws}" "alt.example.test." ZSK active KSK active
      write_previous_manifest "${ws}" 2024071402
      ;;
  esac
}

mkdir -p "${DATA_ROOT}/trust-anchors"
for scenario in normal interrupted rollback wrap altorigin; do
  build_scenario "${scenario}"
done

find "${DATA_ROOT}/workflows" -type f \( -name '*.private' -o -name '*.key' \) -exec chmod a+r {} +

python3 - <<'PY' "${DATA_ROOT}"
import pathlib, re, sys
root = pathlib.Path(sys.argv[1])
ksk = None
for key in (root/'workflows/normal/keys').glob('K*.key'):
    if 'key-signing key' in key.read_text().lower():
        ksk = key; break
if ksk is None:
    for key in (root/'workflows/normal/keys').glob('K*.key'):
        if 'Publish: YES' in key.with_suffix('.private').read_text():
            ksk = key; break
if ksk is None:
    ksk = next((root/'workflows/normal/keys').glob('K*.key'))
text = ksk.read_text()
priv = ksk.with_suffix('.private').read_text()
pub = ''
m = re.search(r'Public-Key:\s*\(?\s*([A-Za-z0-9+/=\s]+)\)?', priv, re.S)
if m:
    pub = ''.join(m.group(1).split())
else:
    chunks = re.findall(r'[A-Za-z0-9+/=]{40,}', text)
    pub = max(chunks, key=len) if chunks else ''
(root/'trust-anchors/example.test.anchor').write_text(f'. IN DNSKEY 257 3 8 {pub}\n')
alt_ksk = None
for key in (root/'workflows/altorigin/keys').glob('K*.key'):
    if 'key-signing key' in key.read_text().lower():
        alt_ksk = key; break
if alt_ksk is None:
    alt_ksk = next((root/'workflows/altorigin/keys').glob('K*.key'))
alt_text = alt_ksk.read_text()
alt_priv = alt_ksk.with_suffix('.private').read_text()
alt_pub = ''
m = re.search(r'Public-Key:\s*\(?\s*([A-Za-z0-9+/=\s]+)\)?', alt_priv, re.S)
if m:
    alt_pub = ''.join(m.group(1).split())
else:
    chunks = re.findall(r'[A-Za-z0-9+/=]{40,}', alt_text)
    alt_pub = max(chunks, key=len) if chunks else ''
(root/'trust-anchors/alt.example.test.anchor').write_text(f'. IN DNSKEY 257 3 8 {alt_pub}\n')
PY

echo "build-visible-fixtures: complete"
