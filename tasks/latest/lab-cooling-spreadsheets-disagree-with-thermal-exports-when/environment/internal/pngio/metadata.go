package pngio

import "path/filepath"

func BaseName(path string) string {
	return filepath.Base(path)
}
