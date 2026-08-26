package parse

import (
	"bytes"
	"encoding/json"
	"fmt"
	"sort"
	"strings"

	"greenhouse-fert-gate/internal/hash"
	"greenhouse-fert-gate/internal/profile"
)

type Event struct {
	EventType        string
	EventSeq         int
	ZoneID           string
	BatchID          string
	CropLabel        string
	OpenedAtUnix     int64
	ClosedAtUnix     int64
	ECmS             float64
	Ph               float64
	VolumeMl         int
	RecordedAtUnix   int64
	LineCRC          string
	RawLine          []byte
}

func ParseLine(line []byte, prof *profile.Profile) (*Event, error) {
	line = bytes.TrimSpace(line)
	if len(line) == 0 {
		return nil, fmt.Errorf("empty line")
	}
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(line, &raw); err != nil {
		return nil, err
	}
	var tmp struct {
		EventType      string  `json:"event_type"`
		EventSeq       int     `json:"event_seq"`
		ZoneID         string  `json:"zone_id"`
		BatchID        string  `json:"batch_id"`
		CropLabel      string  `json:"crop_label"`
		OpenedAtUnix   int64   `json:"opened_at_unix"`
		ClosedAtUnix   int64   `json:"closed_at_unix"`
		ECmS           float64 `json:"ec_mS"`
		Ph             float64 `json:"ph"`
		VolumeMl       int     `json:"volume_ml"`
		RecordedAtUnix int64   `json:"recorded_at_unix"`
		LineCRC        string  `json:"line_crc"`
	}
	if err := json.Unmarshal(line, &tmp); err != nil {
		return nil, err
	}
	ev := Event{
		EventType:      tmp.EventType,
		EventSeq:       tmp.EventSeq,
		ZoneID:         tmp.ZoneID,
		BatchID:        tmp.BatchID,
		CropLabel:      tmp.CropLabel,
		OpenedAtUnix:   tmp.OpenedAtUnix,
		ClosedAtUnix:   tmp.ClosedAtUnix,
		ECmS:           tmp.ECmS,
		Ph:             tmp.Ph,
		VolumeMl:       tmp.VolumeMl,
		RecordedAtUnix: tmp.RecordedAtUnix,
		LineCRC:        tmp.LineCRC,
		RawLine:        append([]byte(nil), line...),
	}
	if ev.EventSeq <= 0 || ev.EventType == "" {
		return nil, fmt.Errorf("missing required field")
	}
	switch ev.EventType {
	case "ZONE_REGISTER":
		if ev.ZoneID == "" || ev.CropLabel == "" {
			return nil, fmt.Errorf("invalid zone register")
		}
	case "BATCH_OPEN":
		if ev.ZoneID == "" || ev.BatchID == "" || ev.OpenedAtUnix <= 0 {
			return nil, fmt.Errorf("invalid batch open")
		}
	case "DOSE_TICK":
		if ev.BatchID == "" || ev.RecordedAtUnix <= 0 {
			return nil, fmt.Errorf("invalid dose tick")
		}
	case "BATCH_CLOSE":
		if ev.BatchID == "" || ev.ClosedAtUnix <= 0 {
			return nil, fmt.Errorf("invalid batch close")
		}
	default:
		return nil, fmt.Errorf("unknown event_type")
	}
	canonical, err := canonicalBytes(raw)
	if err != nil {
		return nil, err
	}
	gotCRC, _ := raw["line_crc"]
	want := hash.CRC16Hex(append(canonical, gotCRC...))
	if !strings.EqualFold(ev.LineCRC, want) {
		return nil, fmt.Errorf("line_crc mismatch")
	}
	_ = prof
	return &ev, nil
}

func canonicalBytes(raw map[string]json.RawMessage) ([]byte, error) {
	keys := make([]string, 0, len(raw))
	for k := range raw {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	var buf bytes.Buffer
	buf.WriteByte('{')
	for i, k := range keys {
		if i > 0 {
			buf.WriteByte(',')
		}
		keyJSON, _ := json.Marshal(k)
		buf.Write(keyJSON)
		buf.WriteByte(':')
		buf.Write(raw[k])
	}
	buf.WriteByte('}')
	return buf.Bytes(), nil
}
