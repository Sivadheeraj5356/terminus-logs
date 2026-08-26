package hlsdrv

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"reelseal/internal/digestutil"
	"reelseal/internal/mediain"
)

func Run(fetchPath, hlsDir string) error {
	raw, err := os.ReadFile(fetchPath)
	if err != nil {
		return err
	}
	var rec mediain.Receipt
	if err := json.Unmarshal(raw, &rec); err != nil {
		return err
	}
	if err := os.MkdirAll(hlsDir, 0o755); err != nil {
		return err
	}
	keyPath := filepath.Join(hlsDir, "key.bin")
	key := make([]byte, 16)
	if _, err := rand.Read(key); err != nil {
		return err
	}
	if err := os.WriteFile(keyPath, key, 0o600); err != nil {
		return err
	}
	iv := make([]byte, 16)
	if _, err := rand.Read(iv); err != nil {
		return err
	}
	ivHex := hex.EncodeToString(iv)
	keyURI := "urn:reelseal:key:rs-pending"
	keyinfo := filepath.Join(hlsDir, "keyinfo.txt")
	if err := os.WriteFile(keyinfo, []byte(keyURI+"\n"+keyPath+"\n"+ivHex+"\n"), 0o644); err != nil {
		return err
	}
	playlist := filepath.Join(hlsDir, "index.m3u8")
	segPattern := filepath.Join(hlsDir, "segment%03d.ts")
	cmd := exec.Command("ffmpeg", "-y", "-i", rec.SourcePath,
		"-c:v", "libx264", "-c:a", "aac", "-f", "hls",
		"-hls_time", "2", "-hls_list_size", "0", "-hls_playlist_type", "vod",
		"-hls_segment_filename", segPattern,
		"-hls_key_info_file", keyinfo,
		playlist,
	)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("ffmpeg: %w: %s", err, string(out))
	}
	if !PlaylistHasAES128(playlist) {
		return fmt.Errorf("playlist missing METHOD=AES-128")
	}
	meta := map[string]string{"iv_hex": ivHex, "key_urn_provisional": keyURI, "media_digest": rec.MediaDigest}
	mb, err := json.MarshalIndent(meta, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(hlsDir, "segment-meta.json"), append(mb, '\n'), 0o644)
}

func PlaylistHasAES128(playlist string) bool {
	b, err := os.ReadFile(playlist)
	if err != nil {
		return false
	}
	return strings.Contains(string(b), "METHOD=AES-128")
}

func HexPlaylist(playlist string) (string, error) {
	return digestutil.HexFile(playlist)
}

func RewriteKeyURN(playlist, keyID string) error {
	b, err := os.ReadFile(playlist)
	if err != nil {
		return err
	}
	urn := "urn:reelseal:key:" + keyID
	s := string(b)
	s = strings.ReplaceAll(s, "urn:reelseal:key:rs-pending", urn)
	s = strings.ReplaceAll(s, "http:\x2f\x2fkeys.decoy.invalid/hls/aes.key", urn)
	return os.WriteFile(playlist, []byte(s), 0o644)
}
