// Package io reads bundle documents without mutating them.
package io

import (
	"encoding/json"
	"fmt"
	"os"

	"plangen/internal/model"
)

// Load parses a bundle document from path. It never writes to path.
func Load(path string) (model.Bundle, error) {
	var b model.Bundle
	data, err := os.ReadFile(path)
	if err != nil {
		return b, err
	}
	if err := json.Unmarshal(data, &b); err != nil {
		return b, fmt.Errorf("parse %s: %w", path, err)
	}
	if err := validate(b); err != nil {
		return b, err
	}
	return b, nil
}

func validate(b model.Bundle) error {
	if b.Unit <= 0 {
		return fmt.Errorf("unit must be positive")
	}
	if b.Bins <= 0 {
		return fmt.Errorf("bins must be positive")
	}
	if b.Cells <= 0 {
		return fmt.Errorf("cells must be positive")
	}
	if b.Lanes <= 0 {
		return fmt.Errorf("lanes must be positive")
	}
	if len(b.Fit) == 0 {
		return fmt.Errorf("fit fold is empty")
	}
	if err := checkRows(b, b.Fit); err != nil {
		return fmt.Errorf("fit fold: %w", err)
	}
	if err := checkRows(b, b.Rim); err != nil {
		return fmt.Errorf("rim: %w", err)
	}
	if err := checkRows(b, b.Hold); err != nil {
		return fmt.Errorf("hold: %w", err)
	}
	if len(b.Hold) == 0 {
		return fmt.Errorf("hold fold is empty")
	}
	for i, r := range b.Rungs {
		if len(r.Rows) == 0 {
			return fmt.Errorf("rung %d has no rows", i)
		}
		if i > 0 && r.Severity <= b.Rungs[i-1].Severity {
			return fmt.Errorf("rung %d severity %d is not above %d", i, r.Severity, b.Rungs[i-1].Severity)
		}
		if r.Span < 0 || r.Span > 2 {
			return fmt.Errorf("rung %d span %d out of range", i, r.Span)
		}
		if err := checkRows(b, r.Rows); err != nil {
			return fmt.Errorf("rung %d: %w", i, err)
		}
	}
	return nil
}

func checkRows(b model.Bundle, rows []model.Row) error {
	for _, r := range rows {
		if r.Raw < 0 || r.Raw > b.Unit {
			return fmt.Errorf("raw %d out of range", r.Raw)
		}
		if r.Hit != 0 && r.Hit != 1 {
			return fmt.Errorf("hit %d not binary", r.Hit)
		}
		if r.Lane < 0 || r.Lane >= b.Lanes {
			return fmt.Errorf("lane %d out of range", r.Lane)
		}
	}
	return nil
}
