package apiclient

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"

	"reelseal/internal/digestutil"
)

type Bind struct {
	Schema       string   `json:"schema"`
	Engine       string   `json:"engine"`
	ProfileID    string   `json:"profile_id"`
	KeyID        string   `json:"key_id"`
	KeyURN       string   `json:"key_urn"`
	SigningAlg   string   `json:"signing_alg"`
	AllowedAlgs  []string `json:"allowed_algs"`
	ProfileEpoch int      `json:"profile_epoch"`
	MediaDigest  string   `json:"media_digest"`
	PolicyDigest string   `json:"policy_digest"`
	KeyURI string `json:"key_uri,omitempty"`
}

func BindPolicy(base, fetchPath, outPath string) error {
	fr, err := os.ReadFile(fetchPath)
	if err != nil {
		return err
	}
	var fetchObj map[string]any
	if err := json.Unmarshal(fr, &fetchObj); err != nil {
		return err
	}
	mediaDigest, _ := fetchObj["media_digest"].(string)
	profileID := "reel-std"
	resolveBody := map[string]any{"profile_id": profileID, "expected_epoch": 0}
	res, err := postJSON(base+"/v1/profiles/resolve", resolveBody)
	if err != nil {
		res = map[string]any{"profile_id": profileID, "epoch": 0, "signing_alg": "HS256", "allowed_algs": []any{"HS256", "Ed25519"}}
	}
	issueBody := map[string]any{"profile_id": profileID, "media_digest": mediaDigest, "purpose": "hls-aes128"}
	iss, err := postJSON(base+"/v1/keys/issue", issueBody)
	if err != nil {
		return err
	}
	epoch, _ := toInt(res["epoch"])
	algs := toStringSlice(res["allowed_algs"])
	bind := Bind{
		Schema:       "reelseal.policy-bind/v1",
		Engine:       "reelseal-runtime/v1",
		ProfileID:    profileID,
		KeyID:        fmt.Sprint(iss["key_id"]),
		KeyURN:       fmt.Sprint(iss["key_urn"]),
		SigningAlg:   fmt.Sprint(res["signing_alg"]),
		AllowedAlgs:  algs,
		ProfileEpoch: epoch,
		MediaDigest:  mediaDigest,
		KeyURI:       fmt.Sprint(iss["key_uri"]), 
	}
	canon, _ := json.Marshal(bind)
	bind.PolicyDigest = digestutil.HexBytes(canon)
	raw, _ := json.MarshalIndent(bind, "", "  ")
	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		return err
	}
	return os.WriteFile(outPath, append(raw, '\n'), 0o644)
}

func postJSON(url string, body any) (map[string]any, error) {
	b, _ := json.Marshal(body)
	resp, err := http.Post(url, "application/json", bytes.NewReader(b))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("http %d: %s", resp.StatusCode, string(data))
	}
	var out map[string]any
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func toInt(v any) (int, bool) {
	switch t := v.(type) {
	case float64:
		return int(t), true
	case int:
		return t, true
	default:
		return 0, false
	}
}

func toStringSlice(v any) []string {
	arr, ok := v.([]any)
	if !ok {
		return nil
	}
	out := make([]string, 0, len(arr))
	for _, x := range arr {
		out = append(out, fmt.Sprint(x))
	}
	return out
}

func Attest(base string, payload map[string]any) (map[string]any, error) {
	return postJSON(base+"/v1/attest/release", payload)
}
