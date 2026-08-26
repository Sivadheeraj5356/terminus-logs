package footer

import (
	"encoding/binary"
	"fmt"

	"fxdesk/internal/model"
)

func ParseFooter(raw []byte) (*model.FooterView, error) {
	if len(raw) < 10 || string(raw[:4]) != "PQX1" {
		return nil, fmt.Errorf("bad magic")
	}
	off := int(binary.LittleEndian.Uint32(raw[4:8]))
	if off >= len(raw) {
		return nil, fmt.Errorf("bad footer offset")
	}
	view := &model.FooterView{
		Raw:     raw,
		Offset:  off,
		Version: raw[8],
	}
	pos := off
	if pos >= len(raw) {
		return nil, fmt.Errorf("empty footer")
	}
	nKeys := int(raw[pos])
	pos++
	for i := 0; i < nKeys; i++ {
		if pos+16 > len(raw) {
			return nil, fmt.Errorf("trunc keys")
		}
		view.Keys = append(view.Keys, append([]byte(nil), raw[pos:pos+16]...))
		pos += 16
	}
	if pos >= len(raw) {
		return nil, fmt.Errorf("no groups")
	}
	nGrp := int(raw[pos])
	pos++
	for i := 0; i < nGrp; i++ {
		if pos+6 > len(raw) {
			return nil, fmt.Errorf("trunc group")
		}
		entry := model.GroupEntry{
			GrpID:   raw[pos],
			KeySlot: raw[pos+1],
			AadSeed: binary.LittleEndian.Uint32(raw[pos+2 : pos+6]),
		}
		view.Groups = append(view.Groups, entry)
		pos += 6
	}
	if pos >= len(raw) {
		return view, nil
	}
	nChunks := int(raw[pos])
	pos++
	for i := 0; i < nChunks; i++ {
		if pos+9 > len(raw) {
			break
		}
		ch := model.ChunkEntry{
			GrpID:  raw[pos],
			Offset: binary.LittleEndian.Uint32(raw[pos+1 : pos+5]),
			Length: binary.LittleEndian.Uint32(raw[pos+5 : pos+9]),
		}
		view.Chunks = append(view.Chunks, ch)
		pos += 9
	}
	return view, nil
}

func KeyMaterial(view *model.FooterView) []byte {
	var out []byte
	for _, k := range view.Keys {
		out = append(out, k...)
	}
	return out
}

func LaneIndex(table *model.IndexTable, grp uint32) (uint32, bool) {
	if table == nil {
		return 0, false
	}
	for _, lane := range table.Lanes {
		if lane.Grp == grp {
			return lane.Idx, true
		}
	}
	return 0, false
}

func DefaultTable(view *model.FooterView) *model.IndexTable {
	lanes := make([]model.Lane, 0, len(view.Groups))
	for _, g := range view.Groups {
		lanes = append(lanes, model.Lane{Grp: uint32(g.GrpID), Idx: uint32(g.KeySlot)})
	}
	return &model.IndexTable{Lanes: lanes, CrossSeed: 0, AadBase: []int{1, 2, 3, 4}}
}
