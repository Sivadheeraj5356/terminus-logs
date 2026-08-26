package k7

import (
	"encoding/binary"
	"fmt"
	"hash/crc32"
	"os"
)

const (
	magic      = "EJ01"
	segSize    = 20
	journalRel = "/app/environment/payload/ring_seg.bin"
)

// Seg is one CRC-covered column-key epoch journal segment.
type Seg struct {
	EpochID  uint32
	Grp      uint8
	KeySlot  uint8
	AadSeed  uint32
	AadEpoch uint32
	Reserved uint16
}

// LoadJournal opens the durable epoch journal.
func LoadJournal(path string) ([]Seg, error) {
	if path == "" {
		path = journalRel
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return decodeJournal(raw)
}

func decodeJournal(raw []byte) ([]Seg, error) {
	if len(raw) < 4 || string(raw[:4]) != magic {
		return nil, fmt.Errorf("bad journal magic")
	}
	var out []Seg
	pos := 4
	for pos+segSize <= len(raw) {
		body := raw[pos : pos+16]
		crcWant := binary.LittleEndian.Uint32(raw[pos+16 : pos+20])
		crcHave := crc32.ChecksumIEEE(body)
		s := Seg{
			EpochID:  binary.LittleEndian.Uint32(body[0:4]),
			Grp:      body[4],
			KeySlot:  body[5],
			AadSeed:  binary.LittleEndian.Uint32(body[6:10]),
			AadEpoch: binary.LittleEndian.Uint32(body[10:14]),
			Reserved: binary.LittleEndian.Uint16(body[14:16]),
		}
		if crcWant != crcHave {
			pos += segSize
			continue
		}
		if s.Reserved != 0 {
			pos += segSize
			continue
		}
		out = append(out, s)
		pos += segSize
	}
	return out, nil
}

// ProjectEpoch returns per-group segments for the active catalog epoch.
func ProjectEpoch(segs []Seg, epochID uint32) (map[uint8]Seg, error) {
	return sel_k(segs, epochID)
}

func sel_k(segs []Seg, epochID uint32) (map[uint8]Seg, error) {
	if len(segs) == 0 {
		return nil, fmt.Errorf("empty journal")
	}
	if epochID == 0 {
		return nil, fmt.Errorf("epoch required")
	}
	out := map[uint8]Seg{}
	seen := map[uint8]bool{}
	for _, s := range segs {
		if s.EpochID != epochID {
			continue
		}
		out[s.Grp] = s
		seen[s.Grp] = true
	}
	if len(seen) == 0 {
		return nil, fmt.Errorf("epoch %d missing", epochID)
	}
	for grp := range out {
		if out[grp].AadEpoch == 0 && out[grp].KeySlot == 0 && out[grp].AadSeed == 0 {
			return nil, fmt.Errorf("empty segment for grp %d", grp)
		}
	}
	return out, nil
}
