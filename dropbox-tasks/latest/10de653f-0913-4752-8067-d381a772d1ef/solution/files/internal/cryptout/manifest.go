package cryptout

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"reelseal/internal/digestutil"
	"reelseal/internal/hlsdrv"
)

type Manifest struct {
	Schema       string         `json:"schema"`
	Engine       string         `json:"engine"`
	MediaDigest  string         `json:"media_digest"`
	PlaylistDig  string         `json:"playlist_digest"`
	KeyID        string         `json:"key_id"`
	KeyURN       string         `json:"key_urn"`
	Method       string         `json:"method"`
	IVHex        string         `json:"iv_hex"`
	PolicyDigest string         `json:"policy_digest"`
	SigningAlg   string         `json:"signing_alg"`
	ProfileEpoch int            `json:"profile_epoch"`
	Provenance   map[string]any `json:"provenance"`
}

func Seal(bindPath, hlsDir, outPath string) error {
	br, err := os.ReadFile(bindPath)
	if err != nil {
		return err
	}
	var bind map[string]any
	if err := json.Unmarshal(br, &bind); err != nil {
		return err
	}
	metaRaw, err := os.ReadFile(filepath.Join(hlsDir, "segment-meta.json"))
	if err != nil {
		return err
	}
	var meta map[string]string
	if err := json.Unmarshal(metaRaw, &meta); err != nil {
		return err
	}
	keyID := str(bind["key_id"])
	playlist := filepath.Join(hlsDir, "index.m3u8")
	if err := hlsdrv.RewriteKeyURN(playlist, keyID); err != nil {
		return err
	}
	pd, err := digestutil.HexFile(playlist)
	if err != nil {
		return err
	}
	if !hlsdrv.PlaylistHasAES128(playlist) {
		return fmt.Errorf("playlist missing AES-128")
	}
	pb, _ := os.ReadFile(playlist)
	if strings.Contains(string(pb), "http:\x2f\x2f") || strings.Contains(string(pb), "https:\x2f\x2f") {
		return fmt.Errorf("playlist still contains http key URI")
	}
	epoch, _ := bind["profile_epoch"].(float64)
	iv := meta["iv_hex"]
	if len(iv) != 32 {
		return fmt.Errorf("iv_hex must be 32 hex chars")
	}
	m := Manifest{
		Schema:       "reelseal.encryption-manifest/v1",
		Engine:       "reelseal-runtime/v1",
		MediaDigest:  str(bind["media_digest"]),
		PlaylistDig:  pd,
		KeyID:        keyID,
		KeyURN:       "urn:reelseal:key:" + keyID,
		Method:       "AES-128",
		IVHex:        strings.ToLower(iv),
		PolicyDigest: str(bind["policy_digest"]),
		SigningAlg:   str(bind["signing_alg"]),
		ProfileEpoch: int(epoch),
		Provenance: map[string]any{
			"attest_id":   "",
			"release_tag": "reelseal-v1.0.0",
		},
	}
	raw, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		return err
	}
	return os.WriteFile(outPath, append(raw, '\n'), 0o644)
}

func str(v any) string {
	if v == nil {
		return ""
	}
	switch t := v.(type) {
	case string:
		return strings.TrimSpace(t)
	default:
		b, _ := json.Marshal(t)
		return strings.TrimSpace(string(b))
	}
}
