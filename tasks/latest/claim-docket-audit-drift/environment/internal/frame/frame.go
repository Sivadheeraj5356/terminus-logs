package frame

import (
	"encoding/json"
	"fmt"

	"example.com/claimdocketaudit/internal/crc"
)

const Magic = "CDKT"

type Payload struct {
	Account     string
	Kind        string
	Region      string
	Seq         int64
	Amount      int64
	HasAmount   bool
	ReplacesSeq int64
	HasReplaces bool
}

type Frame struct {
	Epoch   uint32
	Seq     uint64
	Payload Payload
}

func ParseBlob(blob []byte) (frames []Frame, crcFailures int, err error) {
	off := 0
	for off+26 <= len(blob) {
		if string(blob[off:off+4]) != Magic {
			break
		}
		epoch := uint32(blob[off+6]) | uint32(blob[off+7])<<8 | uint32(blob[off+8])<<16 | uint32(blob[off+9])<<24
		seq := uint64(blob[off+10]) | uint64(blob[off+11])<<8 | uint64(blob[off+12])<<16 | uint64(blob[off+13])<<24 |
			uint64(blob[off+14])<<32 | uint64(blob[off+15])<<40 | uint64(blob[off+16])<<48 | uint64(blob[off+17])<<56
		plen := uint32(blob[off+18]) | uint32(blob[off+19])<<8 | uint32(blob[off+20])<<16 | uint32(blob[off+21])<<24
		end := off + 22 + int(plen)
		if end+4 > len(blob) {
			crcFailures++
			break
		}
		want := uint32(blob[end]) | uint32(blob[end+1])<<8 | uint32(blob[end+2])<<16 | uint32(blob[end+3])<<24
		got := crc.FrameChecksum(blob[off:end])
		if got != want {
			crcFailures++
			off = end + 4
			continue
		}
		var raw map[string]json.RawMessage
		if err := json.Unmarshal(blob[off+22:end], &raw); err != nil {
			return nil, crcFailures, err
		}
		p, err := payloadFromRaw(raw)
		if err != nil {
			return nil, crcFailures, err
		}
		frames = append(frames, Frame{Epoch: epoch, Seq: seq, Payload: p})
		off = end + 4
	}
	return frames, crcFailures, nil
}

func payloadFromRaw(raw map[string]json.RawMessage) (Payload, error) {
	var p Payload
	if err := unmarshalString(raw, "account", &p.Account); err != nil {
		return p, err
	}
	if err := unmarshalString(raw, "kind", &p.Kind); err != nil {
		return p, err
	}
	if err := unmarshalString(raw, "region", &p.Region); err != nil {
		return p, err
	}
	var seq float64
	if err := json.Unmarshal(raw["seq"], &seq); err != nil {
		return p, err
	}
	p.Seq = int64(seq)
	if v, ok := raw["amount"]; ok {
		var amt float64
		if err := json.Unmarshal(v, &amt); err != nil {
			return p, err
		}
		p.Amount = int64(amt)
		p.HasAmount = true
	}
	if v, ok := raw["replaces_seq"]; ok {
		var rep float64
		if err := json.Unmarshal(v, &rep); err != nil {
			return p, err
		}
		p.ReplacesSeq = int64(rep)
		p.HasReplaces = true
	}
	return p, nil
}

func unmarshalString(raw map[string]json.RawMessage, key string, out *string) error {
	v, ok := raw[key]
	if !ok {
		return fmt.Errorf("missing %s", key)
	}
	return json.Unmarshal(v, out)
}

func CanonicalPayloadJSON(p Payload) (string, error) {
	if p.Kind == "tombstone" {
		slim := map[string]any{
			"account": p.Account,
			"kind":    p.Kind,
			"region":  p.Region,
			"seq":     p.Seq,
		}
		raw, err := json.Marshal(slim)
		if err != nil {
			return "", err
		}
		return string(raw), nil
	}
	m := map[string]any{
		"account": p.Account,
		"kind":    p.Kind,
		"region":  p.Region,
		"seq":     p.Seq,
	}
	if p.HasAmount {
		m["amount"] = p.Amount
	}
	if p.HasReplaces {
		m["replaces_seq"] = p.ReplacesSeq
	}
	raw, err := json.Marshal(m)
	if err != nil {
		return "", err
	}
	return string(raw), nil
}
