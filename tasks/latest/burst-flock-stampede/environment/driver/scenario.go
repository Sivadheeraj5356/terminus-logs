package main

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// MatrixRow names one matrix row from matrix_order.txt.
type MatrixRow struct {
	Name string
}

// LoadMatrix reads matrix row identifiers in file order.
func LoadMatrix(fixturesRoot string) ([]MatrixRow, error) {
	path := filepath.Join(fixturesRoot, "matrix_order.txt")
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var out []MatrixRow
	scan := bufio.NewScanner(f)
	for scan.Scan() {
		line := strings.TrimSpace(scan.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		out = append(out, MatrixRow{Name: line})
	}
	if err := scan.Err(); err != nil {
		return nil, err
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("driver: empty matrix")
	}
	return out, nil
}
