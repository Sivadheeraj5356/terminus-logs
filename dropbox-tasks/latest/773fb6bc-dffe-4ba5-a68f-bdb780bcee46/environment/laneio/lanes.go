package laneio

import (
	"fmt"
	"path/filepath"

	cvio "github.com/lab/cvstack/internal/io"
	"github.com/lab/cvstack/internal/model"
)

func FastID(slot int, rows []model.MapRow) int {
	for _, row := range rows {
		if row.A == slot {
			return row.B
		}
	}
	return 0
}

func ReadSlow(ws string, slot int) (model.Slot, error) {
	var s model.Slot
	err := cvio.ReadJSON(filepath.Join(ws, "lanes", "slow", fmt.Sprintf("%d.json", slot)), &s)
	return s, err
}

func ReadFast(ws string, fastID int) (model.Slot, error) {
	var s model.Slot
	err := cvio.ReadJSON(filepath.Join(ws, "lanes", "fast", fmt.Sprintf("%d.json", fastID)), &s)
	return s, err
}

func WriteFast(ws string, s model.Slot) error {
	return cvio.WriteJSON(filepath.Join(ws, "lanes", "fast", fmt.Sprintf("%d.json", s.ID)), s)
}

func SlowPayload(ws string, slot int) string {
	s, err := ReadSlow(ws, slot)
	if err != nil {
		return ""
	}
	return s.Payload
}

func FastPayload(ws string, slot int, rows []model.MapRow) string {
	id := FastID(slot, rows)
	if id == 0 {
		return ""
	}
	s, err := ReadFast(ws, id)
	if err != nil {
		return ""
	}
	return s.Payload
}

func SlowEpoch(ws string, slot int) uint64 {
	s, err := ReadSlow(ws, slot)
	if err != nil {
		return 0
	}
	return s.Epoch
}

func FastEpoch(ws string, slot int, rows []model.MapRow) uint64 {
	id := FastID(slot, rows)
	if id == 0 {
		return 0
	}
	s, err := ReadFast(ws, id)
	if err != nil {
		return 0
	}
	return s.Epoch
}
