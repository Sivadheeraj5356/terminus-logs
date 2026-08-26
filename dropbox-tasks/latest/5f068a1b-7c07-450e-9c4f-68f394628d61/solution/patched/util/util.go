package util

import (
	"fmt"
	"os"
	"path/filepath"
)

func Round4(v float64) float64 {
	return float64(int(v*10000+0.5)) / 10000
}

func AtomicWrite(path string, data []byte) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	tmp, err := os.CreateTemp(dir, ".tmp-*")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		os.Remove(tmpName)
		return err
	}
	if err := tmp.Close(); err != nil {
		os.Remove(tmpName)
		return err
	}
	return os.Rename(tmpName, path)
}

// AtomicCommit writes multiple files atomically: temps are created first and
// final paths are renamed only after every temp write succeeds.
func AtomicCommit(files map[string][]byte) error {
	tmps := make(map[string]string, len(files))
	for final, data := range files {
		dir := filepath.Dir(final)
		if err := os.MkdirAll(dir, 0o755); err != nil {
			cleanup(tmps)
			return err
		}
		tmp, err := os.CreateTemp(dir, ".commit-*")
		if err != nil {
			cleanup(tmps)
			return err
		}
		tmpName := tmp.Name()
		if _, err := tmp.Write(data); err != nil {
			tmp.Close()
			os.Remove(tmpName)
			cleanup(tmps)
			return err
		}
		if err := tmp.Close(); err != nil {
			os.Remove(tmpName)
			cleanup(tmps)
			return err
		}
		tmps[final] = tmpName
	}
	for final, tmp := range tmps {
		if err := os.Rename(tmp, final); err != nil {
			cleanup(tmps)
			return err
		}
		delete(tmps, final)
	}
	return nil
}

func cleanup(tmps map[string]string) {
	for _, tmp := range tmps {
		os.Remove(tmp)
	}
}

func Usage(msg string) {
	fmt.Fprintln(os.Stderr, msg)
	os.Exit(2)
}
