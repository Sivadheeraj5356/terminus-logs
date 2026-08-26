#!/bin/bash
set -euo pipefail
export PATH="/usr/local/go/bin:/opt/verifier/bin:${PATH:-/usr/bin:/bin}"

cat > /app/environment/q8/mux.go <<'EOF'
package q8

import (
	"os"
	"strings"

	"local/ovws/lib"
)

func fragName(query string) string {
	p := strings.Index(query, "frag=")
	if p < 0 {
		return ""
	}
	p += 5
	var b strings.Builder
	for p < len(query) {
		c := query[p]
		if c == ';' || c == ' ' {
			break
		}
		b.WriteByte(c)
		p++
	}
	return b.String()
}

func slotAActive(frag string) bool {
	path := lib.EnvRoot() + "/conf/" + frag + ".conf"
	b, err := os.ReadFile(path)
	if err != nil {
		return false
	}
	for _, line := range strings.Split(string(b), "\n") {
		if strings.HasPrefix(strings.TrimSpace(line), "slot=A") {
			return true
		}
	}
	return false
}

// Mux_q resolves property queries across activated provider arms.
func Mux_q(query string) (string, error) {
	if strings.Contains(query, "strict") {
		frag := fragName(query)
		if frag != "" && slotAActive(frag) {
			return "slotA", nil
		}
	}
	return "def", nil
}
EOF

cat > /app/environment/r4/ord.go <<'EOF'
package r4

import (
	"local/ovws/lib"
)

// Ord_f orders algorithm fetch slots with first-wins dedupe.
func Ord_f(alg string) ([]int, error) {
	_ = alg
	vals, err := lib.SlotValues()
	if err != nil {
		return nil, err
	}
	seen := map[int]bool{}
	var out []int
	for _, v := range vals {
		if seen[v] {
			continue
		}
		seen[v] = true
		out = append(out, v)
	}
	return out, nil
}
EOF

cat > /app/environment/t6/bind.go <<'EOF'
package t6

import "strings"

// Bind_u binds store loader URIs to provider-capable schemes.
func Bind_u(uri, selID string) (string, error) {
	if selID == "slotA" {
		if strings.HasPrefix(uri, "file:") {
			return "file", nil
		}
		return "prv", nil
	}
	if strings.HasPrefix(uri, "prv:") {
		return "prv", nil
	}
	if strings.HasPrefix(uri, "file:") {
		return "file", nil
	}
	return "eng", nil
}
EOF

cat > /app/environment/p2/token.go <<'EOF'
package p2

import (
	"os"
	"strings"
)

const armTokenPath = "/app/output/.ov_persist/arm_token"

func ArmOpen(nonce string) error {
	if nonce == "" {
		return os.ErrInvalid
	}
	if err := os.MkdirAll("/app/output/.ov_persist", 0o755); err != nil {
		return err
	}
	return os.WriteFile(armTokenPath, []byte(nonce), 0o644)
}

func ArmConsume(expected string) error {
	if expected == "" {
		return os.ErrInvalid
	}
	b, err := os.ReadFile(armTokenPath)
	if err != nil {
		return err
	}
	got := strings.TrimSpace(string(b))
	if got != expected {
		return os.ErrInvalid
	}
	return os.Remove(armTokenPath)
}

func ArmTokenPath() string {
	return armTokenPath
}
EOF

cat > /app/environment/p2/latch.go <<'EOF'
package p2

import (
	"os"
	"strings"
)

const latchPath = "/app/output/.ov_persist/pref_latch"

func LatchClear() error {
	return os.Remove(latchPath)
}

func LatchSet(val string) error {
	if err := os.MkdirAll("/app/output/.ov_persist", 0o755); err != nil {
		return err
	}
	return os.WriteFile(latchPath, []byte(val), 0o644)
}

func LatchActive() bool {
	b, err := os.ReadFile(latchPath)
	if err != nil {
		return false
	}
	return len(strings.TrimSpace(string(b))) > 0
}
EOF

cat > /app/environment/p2/journal.go <<'EOF'
package p2

import (
	"os"
	"strings"
)

const (
	jnlPath = "/app/output/.ov_persist/mig.jnl"
	resPath = "/app/output/.ov_persist/rim_residue"
)

func ensurePersist() error {
	return os.MkdirAll("/app/output/.ov_persist", 0o755)
}

func JNote(hex16 string) error {
	if err := ensurePersist(); err != nil {
		return err
	}
	f, err := os.OpenFile(jnlPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.WriteString(hex16 + "\n")
	return err
}

func JReset() error {
	if err := ensurePersist(); err != nil {
		return err
	}
	return os.WriteFile(jnlPath, nil, 0o644)
}

func ResidueGuard() error {
	if err := ensurePersist(); err != nil {
		return err
	}
	p := resPath
	if strings.HasSuffix(p, "/") {
		p = strings.TrimRight(p, "/")
	}
	return os.WriteFile(p, nil, 0o644)
}

func ResidueBody() string {
	b, err := os.ReadFile(resPath)
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(b))
}

func JnlPath() string {
	return jnlPath
}

func ResPath() string {
	return resPath
}
EOF

cat > /app/environment/p2/seal.go <<'EOF'
package p2

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"strconv"

	"local/ovws/lib"
)

const (
	persistDir = "/app/output/.ov_persist"
	bindPath   = persistDir + "/bind_stamp.json"
	genPath    = "/app/environment/var/mig/suite_gen"
	stampPath  = "/app/environment/var/mig/seal_stamp.json"
	idxPath    = "/app/environment/cases/idx.json"
	maskPath   = "/app/environment/var/mig/epoch_mask.json"
)

type bindBlob struct {
	AuthGen int `json:"auth_gen"`
	Epoch   int `json:"epoch"`
}

func EpochExpect() int {
	return lib.SlotSum() ^ lib.ReadMask()
}

func SuiteCycle() int {
	return readGen()
}

func readGen() int {
	b, err := os.ReadFile(genPath)
	if err != nil {
		return 0
	}
	n, _ := strconv.Atoi(string(bytesTrim(b)))
	return n
}

func bytesTrim(b []byte) []byte {
	return []byte(stringsTrim(string(b)))
}

func stringsTrim(s string) string {
	for len(s) > 0 && (s[len(s)-1] == '\n' || s[len(s)-1] == '\r' || s[len(s)-1] == ' ') {
		s = s[:len(s)-1]
	}
	return s
}

func readAuthGen() int {
	b, err := os.ReadFile(bindPath)
	if err != nil {
		return 0
	}
	var obj bindBlob
	if json.Unmarshal(b, &obj) != nil {
		return 0
	}
	return obj.AuthGen
}

func computeNonce() (string, error) {
	ep := strconv.Itoa(EpochExpect())
	idxB, err := os.ReadFile(idxPath)
	if err != nil {
		return "", err
	}
	maskB, err := os.ReadFile(maskPath)
	if err != nil {
		return "", err
	}
	wt := strconv.Itoa(lib.SlotWeight())
	ag := strconv.Itoa(readAuthGen())
	raw := ep + "|" + string(idxB) + "|" + string(maskB) + "|" + wt + "|" + ag
	sum := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(sum[:])[:16], nil
}

func SealPrepare() error {
	if _, err := os.Stat(ArmTokenPath()); err == nil {
		return os.ErrExist
	}
	_ = os.MkdirAll(persistDir, 0o755)
	expected := EpochExpect()
	if b, err := os.ReadFile(stampPath); err == nil {
		var st struct {
			Epoch int `json:"epoch"`
		}
		if json.Unmarshal(b, &st) == nil && st.Epoch != expected {
			_ = os.WriteFile(ResPath(), nil, 0o644)
			_ = JReset()
			_ = LatchClear()
		}
	}
	_ = JReset()
	_ = LatchClear()
	_ = os.WriteFile(ResPath(), nil, 0o644)
	nonce, err := computeNonce()
	if err != nil {
		return err
	}
	return ArmOpen(nonce)
}

func SealFinalize() error {
	nonce, err := computeNonce()
	if err != nil {
		return err
	}
	if err := ArmConsume(nonce); err != nil {
		return err
	}
	_ = LatchSet("sealed")
	gen := readGen()
	newGen := gen + 1
	if err := os.WriteFile(genPath, []byte(strconv.Itoa(newGen)+"\n"), 0o644); err != nil {
		return err
	}
	blob, err := json.Marshal(bindBlob{AuthGen: newGen, Epoch: EpochExpect()})
	if err != nil {
		return err
	}
	return os.WriteFile(bindPath, append(blob, '\n'), 0o644)
}

func BindStampPath() string {
	return bindPath
}

func StampPath() string {
	return stampPath
}
EOF

bash /app/environment/scripts/build_workspace.sh
mkdir -p /app/output
/app/environment/tools/ov_probe/ov_probe --suite all --trace-out /app/output/ov_trace.json
/app/environment/tools/ov_probe/ov_probe --suite rebuild
