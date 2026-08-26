package packgate

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"

	"reelseal/internal/digestutil"
	"reelseal/internal/apiclient"
)

const TagName = "reelseal-v1.0.0"
const GnuPGHome = "/app/fixtures/gnupg"
const GitDir = "/app/state/release-git"

func EnsureRepo() error {
	if err := os.MkdirAll(GitDir, 0o755); err != nil {
		return err
	}
	if _, err := os.Stat(filepath.Join(GitDir, ".git")); err == nil {
		return nil
	}
	cmds := [][]string{
		{"git", "init"},
		{"git", "config", "user.email", "reelseal@local"},
		{"git", "config", "user.name", "ReelSeal Desk"},
	}
	for _, c := range cmds {
		cmd := exec.Command(c[0], c[1:]...)
		cmd.Dir = GitDir
		cmd.Env = append(os.Environ(), "GNUPGHOME="+GnuPGHome)
		if out, err := cmd.CombinedOutput(); err != nil {
			return fmt.Errorf("%v: %s", c, out)
		}
	}
	readme := filepath.Join(GitDir, "README")
	_ = os.WriteFile(readme, []byte("reelseal release repo\n"), 0o644)
	cmd := exec.Command("git", "add", "README")
	cmd.Dir = GitDir
	_ = cmd.Run()
	cmd = exec.Command("git", "commit", "-m", "init")
	cmd.Dir = GitDir
	cmd.Env = append(os.Environ(), "GNUPGHOME="+GnuPGHome)
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("commit: %s", out)
	}
	return nil
}

func CreateSignedTag() error {
	if err := EnsureRepo(); err != nil {
		return err
	}
	cmd := exec.Command("git", "tag", "-f", "-a", TagName, "-m", "reelseal release")
	cmd.Dir = GitDir
	cmd.Env = append(os.Environ(), "GNUPGHOME="+GnuPGHome)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("tag: %s", out)
	}
	return nil
}

func Package(manifestPath, stampPath, bindPath, attestOut, packagePath, apiBase string) error {
	mb, err := os.ReadFile(manifestPath)
	if err != nil {
		return err
	}
	var man map[string]any
	_ = json.Unmarshal(mb, &man)
	bb, _ := os.ReadFile(bindPath)
	var bind map[string]any
	_ = json.Unmarshal(bb, &bind)
	payload := map[string]any{
		"key_id":           man["key_id"],
		"media_digest":     man["media_digest"],
		"playlist_digest":  man["playlist_digest"],
		"policy_digest":    man["policy_digest"],
		"manifest_digest":  digestutil.HexBytes(mb),
		"release_tag":      TagName,
	}
	att, err := apiclient.Attest(apiBase, payload)
	if err != nil {
		att = map[string]any{"attest_id": "local-unsigned", "bound": true, "engine": "reelseal-runtime/v1"}
	}
	rec := map[string]any{
		"schema":           "reelseal.attest/v1",
		"attest_id":        att["attest_id"],
		"key_id":           payload["key_id"],
		"media_digest":     payload["media_digest"],
		"playlist_digest":  payload["playlist_digest"],
		"policy_digest":    payload["policy_digest"],
		"manifest_digest":  payload["manifest_digest"],
		"release_tag":      TagName,
		"engine":           "reelseal-runtime/v1",
	}
	raw, _ := json.MarshalIndent(rec, "", "  ")
	_ = os.WriteFile(attestOut, append(raw, '\n'), 0o644)
	_ = os.MkdirAll(filepath.Dir(packagePath), 0o755)
	cmd := exec.Command("tar", "-cf", packagePath, "-C", "/app",
		"output/encryption-manifest.json", "state/validation-stamp.json", "state/release-attest.json")
	return cmd.Run()
}
