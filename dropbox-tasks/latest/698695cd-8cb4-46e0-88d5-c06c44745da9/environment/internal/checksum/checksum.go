package checksum

import (
	"crypto/sha256"
	"encoding/hex"
	"io"
	"os"
	"path/filepath"
	"sort"
)

func DirectoryDigest(root string) (string, error) {
	var files []string
	err := filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() {
			return nil
		}
		if info.Name() == ".DS_Store" {
			return nil
		}
		rel, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		files = append(files, rel)
		return nil
	})
	if err != nil {
		return "", err
	}
	sort.Strings(files)
	h := sha256.New()
	for _, rel := range files {
		_, _ = io.WriteString(h, rel)
		_, _ = io.WriteString(h, "\n")
		full := filepath.Join(root, rel)
		f, err := os.Open(full)
		if err != nil {
			return "", err
		}
		_, err = io.Copy(h, f)
		f.Close()
		if err != nil {
			return "", err
		}
		_, _ = io.WriteString(h, "\n")
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}
