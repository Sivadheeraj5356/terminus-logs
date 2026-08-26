package cryptout

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"

	"reelseal/internal/digestutil"
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
	KeyURI       string         `json:"key_uri,omitempty"`
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
	_ = json.Unmarshal(metaRaw, &meta)
	playlist := filepath.Join(hlsDir, "index.m3u8")
	pd, err := digestutil.HexFile(playlist)
	if err != nil {
		return err
	}
	epoch, _ := bind["profile_epoch"].(float64)
	m := Manifest{
		Schema:       "reelseal.encryption-manifest/v1",
		Engine:       "reelseal-runtime/v1",
		MediaDigest:  str(bind["media_digest"]),
		PlaylistDig:  pd,
		KeyID:        str(bind["key_id"]),
		KeyURN:       str(bind["key_urn"]),
		Method:       "AES-128",
		IVHex:        meta["iv_hex"],
		PolicyDigest: str(bind["policy_digest"]),
		SigningAlg:   str(bind["signing_alg"]),
		ProfileEpoch: int(epoch),
		Provenance: map[string]any{
			"attest_id":   "",
			"release_tag": "reelseal-v1.0.0",
		},
	}
	if m.KeyURI == "" {
		m.KeyURI = "http:\x2f\x2fkeys.decoy.invalid/hls/aes.key"
	}
	raw, _ := json.MarshalIndent(m, "", "  ")
	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		return err
	}
	return os.WriteFile(outPath, append(raw, '\n'), 0o644)
}

func str(v any) string {
	if v == nil {
		return ""
	}
	return strings.TrimSpace(toS(v))
}

func toS(v any) string {
	switch t := v.(type) {
	case string:
		return t
	default:
		b, _ := json.Marshal(t)
		return string(b)
	}
}
