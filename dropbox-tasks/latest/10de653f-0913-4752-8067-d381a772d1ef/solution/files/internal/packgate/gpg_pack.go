package packgate

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"reelseal/internal/digestutil"
	"reelseal/internal/stampv"
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
		{"git", "config", "user.signingkey", ""},
		{"git", "config", "gpg.program", "gpg"},
	}
	for _, c := range cmds {
		cmd := exec.Command(c[0], c[1:]...)
		cmd.Dir = GitDir
		cmd.Env = append(os.Environ(), "GNUPGHOME="+GnuPGHome)
		if out, err := cmd.CombinedOutput(); err != nil {
			return fmt.Errorf("%v: %s", c, out)
		}
	}
	fp, err := primaryKeyFP()
	if err != nil {
		return err
	}
	cmd := exec.Command("git", "config", "user.signingkey", fp)
	cmd.Dir = GitDir
	cmd.Env = append(os.Environ(), "GNUPGHOME="+GnuPGHome)
	_ = cmd.Run()
	readme := filepath.Join(GitDir, "README")
	if err := os.WriteFile(readme, []byte("reelseal release repo\n"), 0o644); err != nil {
		return err
	}
	cmd = exec.Command("git", "add", "README")
	cmd.Dir = GitDir
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("add: %s", out)
	}
	cmd = exec.Command("git", "commit", "-m", "init")
	cmd.Dir = GitDir
	cmd.Env = append(os.Environ(), "GNUPGHOME="+GnuPGHome)
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("commit: %s", out)
	}
	return nil
}

func primaryKeyFP() (string, error) {
	cmd := exec.Command("gpg", "--list-secret-keys", "--with-colons")
	cmd.Env = append(os.Environ(), "GNUPGHOME="+GnuPGHome)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("gpg list: %s", out)
	}
	for _, line := range strings.Split(string(out), "\n") {
		if strings.HasPrefix(line, "fpr:") {
			parts := strings.Split(line, ":")
			if len(parts) > 9 && parts[9] != "" {
				return parts[9], nil
			}
		}
	}
	return "", fmt.Errorf("no gpg fingerprint")
}

func CreateSignedTag() error {
	if err := EnsureRepo(); err != nil {
		return err
	}
	fp, err := primaryKeyFP()
	if err != nil {
		return err
	}
	_ = exec.Command("git", "tag", "-d", TagName).Run()
	cmd := exec.Command("git", "tag", "-s", TagName, "-m", "reelseal release")
	cmd.Dir = GitDir
	cmd.Env = append(os.Environ(), "GNUPGHOME="+GnuPGHome, "GIT_COMMITTER_NAME=ReelSeal Desk", "GIT_COMMITTER_EMAIL=reelseal@local")
	_ = exec.Command("git", "-C", GitDir, "config", "user.signingkey", fp).Run()
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("signed tag: %s", out)
	}
	return VerifyTag()
}

func VerifyTag() error {
	cmd := exec.Command("git", "verify-tag", TagName)
	cmd.Dir = GitDir
	cmd.Env = append(os.Environ(), "GNUPGHOME="+GnuPGHome)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("verify-tag failed: %s", out)
	}
	return nil
}

func Package(manifestPath, stampPath, bindPath, attestOut, packagePath, apiBase string) error {
	if err := VerifyTag(); err != nil {
		return err
	}
	sb, err := os.ReadFile(stampPath)
	if err != nil {
		return err
	}
	var stamp map[string]any
	if err := json.Unmarshal(sb, &stamp); err != nil {
		return err
	}
	if stamp["accepted"] != true {
		return fmt.Errorf("stamp not accepted")
	}
	mb, err := os.ReadFile(manifestPath)
	if err != nil {
		return err
	}
	var man map[string]any
	if err := json.Unmarshal(mb, &man); err != nil {
		return err
	}
	for _, f := range []string{"key_uri", "key_url"} {
		if _, ok := man[f]; ok {
			return fmt.Errorf("manifest still has %s", f)
		}
	}
	payload := map[string]any{
		"key_id":          man["key_id"],
		"media_digest":    man["media_digest"],
		"playlist_digest": man["playlist_digest"],
		"policy_digest":   man["policy_digest"],
		"manifest_digest": digestutil.HexBytes(mb),
		"release_tag":     TagName,
	}
	att, err := apiclient.Attest(apiBase, payload)
	if err != nil {
		return fmt.Errorf("attest: %w", err)
	}
	rec := map[string]any{
		"schema":          "reelseal.attest/v1",
		"attest_id":       att["attest_id"],
		"key_id":          payload["key_id"],
		"media_digest":    payload["media_digest"],
		"playlist_digest": payload["playlist_digest"],
		"policy_digest":   payload["policy_digest"],
		"manifest_digest": payload["manifest_digest"],
		"release_tag":     TagName,
		"engine":          "reelseal-runtime/v1",
	}
	raw, err := json.MarshalIndent(rec, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(attestOut, append(raw, '\n'), 0o644); err != nil {
		return err
	}
	man["provenance"] = map[string]any{"attest_id": att["attest_id"], "release_tag": TagName}
	mb2, err := json.MarshalIndent(man, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(manifestPath, append(mb2, '\n'), 0o644); err != nil {
		return err
	}
	if err := stampv.Check(manifestPath, stampPath); err != nil {
		return fmt.Errorf("re-stamp: %w", err)
	}
	if err := os.MkdirAll(filepath.Dir(packagePath), 0o755); err != nil {
		return err
	}
	cmd := exec.Command("tar", "-cf", packagePath, "-C", "/app",
		"output/encryption-manifest.json", "state/validation-stamp.json", "state/release-attest.json")
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("tar: %s", out)
	}
	return nil
}
