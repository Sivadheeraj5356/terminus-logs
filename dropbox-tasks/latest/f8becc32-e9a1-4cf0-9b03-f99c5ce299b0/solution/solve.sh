#!/bin/bash
set -euo pipefail

cd /app

cat > /app/cantrace.go <<'GO'
package main

import (
	"encoding/binary"
	"encoding/json"
	"fmt"
	"math"
	"path/filepath"
	"os"
)

type Network struct {
	Bus      string    `json:"bus"`
	Messages []Message `json:"messages"`
}

type Message struct {
	ID          int       `json:"id"`
	Name        string    `json:"name"`
	ExpectedDLC int       `json:"expected_dlc"`
	MaxGapMS    *uint32   `json:"max_gap_ms"`
	Counter     *Counter  `json:"counter"`
	CounterGroup string `json:"counter_group"`
	CounterReset *CounterReset `json:"counter_reset"`
	Checksum    *Checksum `json:"checksum"`
	ListenOnlyFlags bool `json:"listen_only_flags"`
	CounterHoldFlags bool `json:"counter_hold_flags"`
	StatsResetFlags bool `json:"stats_reset_flags"`
	Signals     []Signal  `json:"signals"`
}

type Counter struct {
	Byte   int `json:"byte"`
	Mask   int `json:"mask"`
	Shift  int `json:"shift"`
	Modulo int `json:"modulo"`
}

type Checksum struct {
	Byte int    `json:"byte"`
	Mode string `json:"mode"`
	Seed int    `json:"seed"`
	FinalXor int `json:"final_xor"`
}

type CounterReset struct {
	Byte  int `json:"byte"`
	Mask  int `json:"mask"`
	Value int `json:"value"`
}

type Mux struct {
	Byte  int `json:"byte"`
	Mask  int `json:"mask"`
	Value int `json:"value"`
}

type Signal struct {
	Name     string  `json:"name"`
	StartBit int     `json:"start_bit"`
	Length   int     `json:"length"`
	Endian   string  `json:"endian"`
	Signed   bool    `json:"signed"`
	Scale    float64 `json:"scale"`
	Offset   float64 `json:"offset"`
	Unit     string  `json:"unit"`
	Mux      *Mux    `json:"mux"`
	InvalidRaw []int `json:"invalid_raw"`
	MaxDelta *float64 `json:"max_delta"`
}

type Warning struct {
	TimestampMS uint32 `json:"timestamp_ms"`
	Reason      string `json:"reason"`
	Detail      string `json:"detail"`
}

type SignalOut struct {
	Name            string   `json:"name"`
	Unit            string   `json:"unit"`
	Count           int      `json:"count"`
	Min             *float64 `json:"min"`
	Max             *float64 `json:"max"`
	Last            *float64 `json:"last"`
	LastTimestampMS *uint32  `json:"last_timestamp_ms"`
}

type MessageOut struct {
	ID          int         `json:"id"`
	Name        string      `json:"name"`
	Frames      int         `json:"frames"`
	ValidFrames int         `json:"valid_frames"`
	Warnings    []Warning   `json:"warnings"`
	Signals     []SignalOut `json:"signals"`
}

type UnknownFrame struct {
	TimestampMS uint32 `json:"timestamp_ms"`
	ID          int    `json:"id"`
	DLC         int    `json:"dlc"`
	Reason      string `json:"reason"`
}

type Report struct {
	Bus           string         `json:"bus"`
	Messages      []MessageOut   `json:"messages"`
	UnknownFrames []UnknownFrame `json:"unknown_frames"`
}

type frame struct {
	ts      uint32
	id      int
	dlc     int
	flags   int
	payload [8]byte
}

type sigState struct {
	out SignalOut
}

func main() {
	networkPath := "/app/task_file/network.json"
	tracePath := "/app/task_file/public_trace.bin"
	outPath := "/app/out/report.json"
	if len(os.Args) == 4 {
		networkPath = os.Args[1]
		tracePath = os.Args[2]
		outPath = os.Args[3]
	} else if len(os.Args) != 1 {
		fatalf("usage: /app/cantrace [network.json trace.bin report.json]")
	}

	var net Network
	readJSON(networkPath, &net)
	frames := readFrames(tracePath)
	report := decode(net, frames)

	data, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		fatalf("marshal report: %v", err)
	}
	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		fatalf("create output dir %s: %v", filepath.Dir(outPath), err)
	}
	if err := os.WriteFile(outPath, append(data, '\n'), 0o644); err != nil {
		fatalf("write report: %v", err)
	}
}

func readJSON(path string, dst any) {
	data, err := os.ReadFile(path)
	if err != nil {
		fatalf("read %s: %v", path, err)
	}
	if err := json.Unmarshal(data, dst); err != nil {
		fatalf("parse %s: %v", path, err)
	}
}

func readFrames(path string) []frame {
	data, err := os.ReadFile(path)
	if err != nil {
		fatalf("read %s: %v", path, err)
	}
	if len(data)%16 != 0 {
		fatalf("trace length %d is not a multiple of 16", len(data))
	}
	frames := make([]frame, 0, len(data)/16)
	for off := 0; off < len(data); off += 16 {
		var f frame
		f.ts = binary.LittleEndian.Uint32(data[off : off+4])
		f.id = int(binary.LittleEndian.Uint16(data[off+4 : off+6]))
		f.dlc = int(data[off+6])
		f.flags = int(data[off+7])
		copy(f.payload[:], data[off+8:off+16])
		frames = append(frames, f)
	}
	return frames
}

func decode(net Network, frames []frame) Report {
	report := Report{Bus: net.Bus, Messages: []MessageOut{}, UnknownFrames: []UnknownFrame{}}
	msgIndex := map[int]int{}
	sigStates := make([][]sigState, len(net.Messages))
	prevCounters := map[string]*int{}
	counterScopes := make([]string, len(net.Messages))
	prevValidTS := make([]*uint32, len(net.Messages))

	for i, msg := range net.Messages {
		msgIndex[msg.ID] = i
		if msg.Counter != nil {
			if msg.CounterGroup != "" {
				counterScopes[i] = "group:" + msg.CounterGroup
			} else {
				counterScopes[i] = fmt.Sprintf("message:%d", i)
			}
		}
		out := MessageOut{ID: msg.ID, Name: msg.Name, Warnings: []Warning{}, Signals: []SignalOut{}}
		for _, sig := range msg.Signals {
			out.Signals = append(out.Signals, SignalOut{Name: sig.Name, Unit: sig.Unit})
		}
		report.Messages = append(report.Messages, out)
		states := make([]sigState, len(msg.Signals))
		for j, sig := range msg.Signals {
			states[j].out = SignalOut{Name: sig.Name, Unit: sig.Unit}
		}
		sigStates[i] = states
	}

	for _, f := range frames {
		mi, ok := msgIndex[f.id]
		if !ok {
			report.UnknownFrames = append(report.UnknownFrames, UnknownFrame{
				TimestampMS: f.ts,
				ID:          f.id,
				DLC:         f.dlc,
				Reason:      "unknown_id",
			})
			continue
		}
		msg := net.Messages[mi]
		out := &report.Messages[mi]
		out.Frames++

		if f.dlc != msg.ExpectedDLC || f.dlc < 0 || f.dlc > 8 {
			out.Warnings = append(out.Warnings, Warning{TimestampMS: f.ts, Reason: "dlc_mismatch", Detail: ""})
			continue
		}
		if msg.Checksum != nil && !checksumOK(f.payload, f.dlc, *msg.Checksum) {
			out.Warnings = append(out.Warnings, Warning{TimestampMS: f.ts, Reason: "bad_checksum", Detail: ""})
			continue
		}

		out.ValidFrames++
		if msg.MaxGapMS != nil {
			if prevValidTS[mi] != nil {
				delta := int64(f.ts) - int64(*prevValidTS[mi])
				if delta > int64(*msg.MaxGapMS) {
					out.Warnings = append(out.Warnings, Warning{TimestampMS: f.ts, Reason: "stale_gap", Detail: ""})
				}
			}
			t := f.ts
			prevValidTS[mi] = &t
		}
		counterHold := msg.CounterHoldFlags && f.flags&0x02 != 0
		if counterHold {
			out.Warnings = append(out.Warnings, Warning{TimestampMS: f.ts, Reason: "counter_hold", Detail: ""})
		}
		if msg.Counter != nil && !counterHold {
			observed := (int(f.payload[msg.Counter.Byte]) & msg.Counter.Mask) >> msg.Counter.Shift
			reset := counterResetMatches(f.payload, msg.CounterReset)
			scope := counterScopes[mi]
			if !reset && prevCounters[scope] != nil {
				expected := (*prevCounters[scope] + 1) % msg.Counter.Modulo
				if observed != expected {
					out.Warnings = append(out.Warnings, Warning{TimestampMS: f.ts, Reason: "counter_jump", Detail: ""})
				}
			}
			v := observed
			prevCounters[scope] = &v
		}

		if msg.StatsResetFlags && f.flags&0x04 != 0 {
			out.Warnings = append(out.Warnings, Warning{TimestampMS: f.ts, Reason: "stats_reset", Detail: ""})
			resetSignalStates(sigStates[mi], msg)
		}

		if msg.ListenOnlyFlags && f.flags&0x01 != 0 {
			out.Warnings = append(out.Warnings, Warning{TimestampMS: f.ts, Reason: "listen_only", Detail: ""})
			continue
		}

		for si, sig := range msg.Signals {
			if sig.Mux != nil {
				got := int(f.payload[sig.Mux.Byte]) & sig.Mux.Mask
				if got != sig.Mux.Value {
					continue
				}
			}
			raw := rawValue(f.payload, sig)
			if containsInt(sig.InvalidRaw, int(raw)) {
				continue
			}
			value := physicalFromRaw(raw, sig)
			current := cleanNumber(value)
			if sig.MaxDelta != nil && sigStates[mi][si].out.Count > 0 && sigStates[mi][si].out.Last != nil {
				if math.Abs(current-*sigStates[mi][si].out.Last) > *sig.MaxDelta {
					out.Warnings = append(out.Warnings, Warning{TimestampMS: f.ts, Reason: "signal_jump", Detail: ""})
				}
			}
			updateSignal(&sigStates[mi][si].out, value, f.ts)
		}
	}

	for mi := range report.Messages {
		for si := range report.Messages[mi].Signals {
			report.Messages[mi].Signals[si] = sigStates[mi][si].out
		}
	}
	return report
}

func checksumOK(payload [8]byte, dlc int, cfg Checksum) bool {
	if cfg.Byte < 0 || cfg.Byte >= len(payload) {
		return false
	}
	switch cfg.Mode {
	case "sum8":
		sum := cfg.Seed % 256
		for i := 0; i < dlc; i++ {
			if i != cfg.Byte {
				sum = (sum + int(payload[i])) % 256
			}
		}
		return byte(sum) == payload[cfg.Byte]
	case "xor8":
		value := cfg.Seed & 0xFF
		for i := 0; i < dlc; i++ {
			if i != cfg.Byte {
				value ^= int(payload[i])
			}
		}
		return byte(value&0xFF) == payload[cfg.Byte]
	case "crc8":
		value := cfg.Seed & 0xFF
		for i := 0; i < dlc; i++ {
			if i == cfg.Byte {
				continue
			}
			value ^= int(payload[i])
			for bit := 0; bit < 8; bit++ {
				if value&0x80 != 0 {
					value = ((value << 1) ^ 0x1D) & 0xFF
				} else {
					value = (value << 1) & 0xFF
				}
			}
		}
		value = (value ^ cfg.FinalXor) & 0xFF
		return byte(value) == payload[cfg.Byte]
	default:
		return false
	}
}

func counterResetMatches(payload [8]byte, reset *CounterReset) bool {
	if reset == nil {
		return false
	}
	return (int(payload[reset.Byte]) & reset.Mask) == reset.Value
}

func rawValue(payload [8]byte, sig Signal) uint64 {
	raw := uint64(0)
	if sig.Endian == "big" {
		for i := 0; i < sig.Length; i++ {
			pos := sig.StartBit + i
			bit := uint64(0)
			if (payload[pos/8] & byte(1<<(7-(pos%8)))) != 0 {
				bit = 1
			}
			raw = (raw << 1) | bit
		}
	} else {
		for i := 0; i < sig.Length; i++ {
			pos := sig.StartBit + i
			if (payload[pos/8] & byte(1<<(pos%8))) != 0 {
				raw |= uint64(1) << i
			}
		}
	}
	return raw
}

func physicalFromRaw(raw uint64, sig Signal) float64 {
	var signed int64
	if sig.Signed && sig.Length > 0 && ((raw>>(sig.Length-1))&1) == 1 {
		signed = int64(raw) - (int64(1) << sig.Length)
	} else {
		signed = int64(raw)
	}
	return float64(signed)*sig.Scale + sig.Offset
}

func containsInt(values []int, target int) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}

func updateSignal(out *SignalOut, value float64, ts uint32) {
	v := cleanNumber(value)
	if out.Count == 0 {
		out.Min = &v
		out.Max = &v
	} else {
		if v < *out.Min {
			out.Min = &v
		}
		if v > *out.Max {
			out.Max = &v
		}
	}
	out.Count++
	out.Last = &v
	t := ts
	out.LastTimestampMS = &t
}

func resetSignalStates(states []sigState, msg Message) {
	for i, sig := range msg.Signals {
		states[i].out = SignalOut{Name: sig.Name, Unit: sig.Unit}
	}
}

func cleanNumber(v float64) float64 {
	if math.Abs(v) == 0 {
		return 0
	}
	return v
}

func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
	os.Exit(2)
}
GO

gofmt -w /app/cantrace.go
go build -o /app/cantrace /app/cantrace.go
/app/cantrace
