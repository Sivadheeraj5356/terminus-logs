package cstore

import (
	"encoding/json"
	"os"

	"missiondesk/lib/model"
)

type StateFile map[string]model.CaseState

func LoadState(path string, reset bool) (StateFile, error) {
	if reset {
		return StateFile{}, nil
	}
	data, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return StateFile{}, nil
	}
	if err != nil {
		return nil, err
	}
	var sf StateFile
	if err := json.Unmarshal(data, &sf); err != nil {
		return nil, err
	}
	return sf, nil
}

func SaveState(path string, sf StateFile) error {
	data, err := json.MarshalIndent(sf, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0o644)
}

func StateFor(sf StateFile, caseID string) model.CaseState {
	st := sf["active"]
	if st.CaseID == "" {
		st.CaseID = caseID
	}
	return st
}

func PutState(sf StateFile, st model.CaseState) {
	sf["active"] = st
}
