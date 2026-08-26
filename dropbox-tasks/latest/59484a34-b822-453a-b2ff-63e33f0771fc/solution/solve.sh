# Oracle solve — task identity ct-pki-trust-evidence-reconstructor token b161aa7f
#!/bin/bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/app}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cat > "${APP_ROOT}/internal/merkle/verify.go" <<'EOF'
package merkle

import (
	"crypto/sha256"
	"encoding/hex"
)

func LeafHash(serial string, leafIndex int, leafPayload string) string {
	h := sha256.New()
	h.Write([]byte(serial))
	h.Write([]byte("|"))
	h.Write([]byte(leafPayload))
	return hex.EncodeToString(h.Sum(nil))
}

func decodeHex32(s string) ([]byte, error) {
	return hex.DecodeString(s)
}

func parentHash(left, right []byte) string {
	h := sha256.New()
	h.Write(left)
	h.Write(right)
	return hex.EncodeToString(h.Sum(nil))
}

func VerifyPath(leafHash string, leafIndex int, path []string, rootHash string, treeSize int) bool {
	if treeSize <= 0 || leafIndex < 0 || leafIndex >= treeSize {
		return false
	}
	curBytes, err := decodeHex32(leafHash)
	if err != nil {
		return false
	}
	cur := leafHash
	idx := leafIndex
	for _, sibling := range path {
		sibBytes, err := decodeHex32(sibling)
		if err != nil {
			return false
		}
		if idx%2 == 0 {
			cur = parentHash(curBytes, sibBytes)
		} else {
			cur = parentHash(sibBytes, curBytes)
		}
		curBytes, err = decodeHex32(cur)
		if err != nil {
			return false
		}
		idx = idx / 2
	}
	return cur == rootHash
}
EOF

cd "${SCRIPT_DIR}"
bash ./apply_oracle.sh

cd "${APP_ROOT}"
go build -a -o /app/bin/ctpki ./cmd/ctpki

BUNDLE="/app/fixtures/bundle-migration-alpha"
SNAPSHOT="/app/state/pki-evidence/ct_merkle_snapshot.json"
REPORT="/app/state/pki-evidence/disposition_matrix.json"
OUT="/app/output/published_ct_ledger.json"

mkdir -p /app/state/pki-evidence /app/output

/app/scripts/pki_migration_bundle_gate.sh "${BUNDLE}"
/app/bin/ctpki attest --bundle "${BUNDLE}" --snapshot "${SNAPSHOT}" --report "${REPORT}"
/app/bin/ctpki publish --report "${REPORT}" --snapshot "${SNAPSHOT}" --out "${OUT}"

test -f "${SNAPSHOT}"
test -f "${REPORT}"
test -f "${OUT}"
test -x /app/bin/ctpki
