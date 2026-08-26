package io

import (
	"encoding/json"
	"os"
	"path/filepath"

	"fxdesk/internal/model"
)

const Root = "/app/environment"

func LoadCases() (*model.CaseIndex, error) {
	return loadCasesFile(filepath.Join(Root, "payload/cases.json"))
}

func loadCasesFile(path string) (*model.CaseIndex, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var idx model.CaseIndex
	if err := json.Unmarshal(raw, &idx); err != nil {
		return nil, err
	}
	return &idx, nil
}

func LoadCase(id string) (*model.CaseSpec, error) {
	idx, err := LoadCases()
	if err != nil {
		return nil, err
	}
	for _, e := range idx.Entries {
		if e.ID == id {
			cp := e
			return &cp, nil
		}
	}
	return nil, os.ErrNotExist
}

func ReadRel(rel string) ([]byte, error) {
	return os.ReadFile(filepath.Join(Root, rel))
}

func LoadSidecar(rel string) (*model.IndexTable, error) {
	raw, err := ReadRel(rel)
	if err != nil {
		return nil, err
	}
	var table model.IndexTable
	if err := json.Unmarshal(raw, &table); err != nil {
		return nil, err
	}
	return &table, nil
}

func AbsRel(rel string) string {
	return filepath.Join(Root, rel)
}
