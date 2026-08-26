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
	rosterEpoch := 7
	if b, err := os.ReadFile("/app/fixtures/profiles/roster.json"); err == nil {
		var rost map[string]any
		if json.Unmarshal(b, &rost) == nil {
			if e, ok := toInt(rost["epoch"]); ok {
				rosterEpoch = e
			}
			if p, ok := rost["profile_id"].(string); ok && p != "" {
				profileID = p
			}
		}
	}
	resolveBody := map[string]any{"profile_id": profileID, "expected_epoch": rosterEpoch}
	res, err := postJSON(base+"/v1/profiles/resolve", resolveBody)
	if err != nil {
		return fmt.Errorf("resolve: %w", err)
	}
	issueBody := map[string]any{"profile_id": profileID, "media_digest": mediaDigest, "purpose": "hls-aes128"}
	iss, err := postJSON(base+"/v1/keys/issue", issueBody)
	if err != nil {
		return fmt.Errorf("issue: %w", err)
	}
	if _, bad := iss["key_uri"]; bad {
		return fmt.Errorf("policy API leaked key_uri")
	}
	epoch, _ := toInt(res["epoch"])
	algs := toStringSlice(res["allowed_algs"])
	signing := fmt.Sprint(res["signing_alg"])
	okAlg := false
	for _, a := range algs {
		if a == signing {
			okAlg = true
			break
		}
	}
	if !okAlg {
		return fmt.Errorf("signing_alg %s not in allowed_algs", signing)
	}
	bind := Bind{
		Schema:       "reelseal.policy-bind/v1",
		Engine:       "reelseal-runtime/v1",
		ProfileID:    profileID,
		KeyID:        fmt.Sprint(iss["key_id"]),
		KeyURN:       fmt.Sprint(iss["key_urn"]),
		SigningAlg:   signing,
		AllowedAlgs:  algs,
		ProfileEpoch: epoch,
		MediaDigest:  mediaDigest,
	}
	tmp := map[string]any{
		"schema": bind.Schema, "engine": bind.Engine, "profile_id": bind.ProfileID,
		"key_id": bind.KeyID, "key_urn": bind.KeyURN, "signing_alg": bind.SigningAlg,
		"allowed_algs": bind.AllowedAlgs, "profile_epoch": bind.ProfileEpoch,
		"media_digest": bind.MediaDigest,
	}
	canon, err := json.Marshal(tmp)
	if err != nil {
		return err
	}
	bind.PolicyDigest = digestutil.HexBytes(canon)
	raw, err := json.MarshalIndent(bind, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		return err
	}
	return os.WriteFile(outPath, append(raw, '\n'), 0o644)
}

func postJSON(url string, body any) (map[string]any, error) {
	b, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}
	resp, err := http.Post(url, "application/json", bytes.NewReader(b))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
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
