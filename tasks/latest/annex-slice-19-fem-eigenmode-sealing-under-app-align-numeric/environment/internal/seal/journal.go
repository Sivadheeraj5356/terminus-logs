package seal

import (
	"encoding/binary"
	"encoding/json"
	"fmt"
	"hash/crc32"
	"os"
	"path/filepath"
)

const journalMagic = "MDJL"

type Frame struct {
	Generation uint64
	Payload    string
}

type HeadState struct {
	Generation            uint64
	DigestFull            string
	TableHash             string
	ChainDigest           string
	EpochBind             string
	LineageID             uint64
	TotalBoundViolations int
	FramesKept            int
	Recovered             bool
}

func frameCRC(generation uint64, payload string) uint32 {
	buf := make([]byte, 8+4+len(payload))
	binary.LittleEndian.PutUint64(buf[0:8], generation)
	binary.LittleEndian.PutUint32(buf[8:12], uint32(len(payload)))
	copy(buf[12:], payload)
	return crc32.ChecksumIEEE(buf)
}

func appendFrame(journal string, frame Frame) error {
	exists := false
	if st, err := os.Stat(journal); err == nil && st.Size() > 0 {
		exists = true
	}
	f, err := os.OpenFile(journal, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	if !exists {
		if _, err := f.Write([]byte(journalMagic)); err != nil {
			return err
		}
		ver := make([]byte, 4)
		binary.LittleEndian.PutUint32(ver, 2)
		if _, err := f.Write(ver); err != nil {
			return err
		}
	}
	gen := make([]byte, 8)
	binary.LittleEndian.PutUint64(gen, frame.Generation)
	if _, err := f.Write(gen); err != nil {
		return err
	}
	ln := make([]byte, 4)
	binary.LittleEndian.PutUint32(ln, uint32(len(frame.Payload)))
	if _, err := f.Write(ln); err != nil {
		return err
	}
	if _, err := f.Write([]byte(frame.Payload)); err != nil {
		return err
	}
	crc := make([]byte, 4)
	binary.LittleEndian.PutUint32(crc, frameCRC(frame.Generation, frame.Payload))
	_, err = f.Write(crc)
	return err
}

func loadFrames(journal string) ([]Frame, error) {
	raw, err := os.ReadFile(journal)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	if len(raw) == 0 {
		return nil, nil
	}
	if len(raw) < 8 || string(raw[0:4]) != journalMagic {
		return nil, fmt.Errorf("bad journal magic")
	}
	off := 8
	var kept []Frame
	for off < len(raw) {
		if off+12 > len(raw) {
			break
		}
		gen := binary.LittleEndian.Uint64(raw[off : off+8])
		off += 8
		ln := int(binary.LittleEndian.Uint32(raw[off : off+4]))
		off += 4
		if ln < 0 || off+ln+4 > len(raw) {
			break
		}
		payload := string(raw[off : off+ln])
		off += ln
		got := binary.LittleEndian.Uint32(raw[off : off+4])
		off += 4
		if got != frameCRC(gen, payload) {
			break
		}
		kept = append(kept, Frame{Generation: gen, Payload: payload})
	}
	return compactIntact(kept), nil
}

func compactIntact(frames []Frame) []Frame {
	var kept []Frame
	var last uint64
	have := false
	for _, f := range frames {
		if f.Payload == "" {
			continue
		}
		if have && f.Generation <= last {
			continue
		}
		kept = append(kept, f)
		last = f.Generation
		have = true
	}
	return kept
}

func expectedJournalBytes(frames []Frame) int {
	n := 8
	for _, f := range frames {
		n += 8 + 4 + len(f.Payload) + 4
	}
	return n
}

func rewriteFrames(journal string, frames []Frame) error {
	tmp := journal + ".tmp"
	_ = os.Remove(tmp)
	f, err := os.OpenFile(tmp, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
	if err != nil {
		return err
	}
	if _, err := f.Write([]byte(journalMagic)); err != nil {
		f.Close()
		return err
	}
	ver := make([]byte, 4)
	binary.LittleEndian.PutUint32(ver, 2)
	if _, err := f.Write(ver); err != nil {
		f.Close()
		return err
	}
	for _, frame := range frames {
		gen := make([]byte, 8)
		binary.LittleEndian.PutUint64(gen, frame.Generation)
		if _, err := f.Write(gen); err != nil {
			f.Close()
			return err
		}
		ln := make([]byte, 4)
		binary.LittleEndian.PutUint32(ln, uint32(len(frame.Payload)))
		if _, err := f.Write(ln); err != nil {
			f.Close()
			return err
		}
		if _, err := f.Write([]byte(frame.Payload)); err != nil {
			f.Close()
			return err
		}
		crc := make([]byte, 4)
		binary.LittleEndian.PutUint32(crc, frameCRC(frame.Generation, frame.Payload))
		if _, err := f.Write(crc); err != nil {
			f.Close()
			return err
		}
	}
	if err := f.Close(); err != nil {
		return err
	}
	return os.Rename(tmp, journal)
}

func recoverHead(journal, tipJSON, bindPath string) (HeadState, error) {
	var tip HeadState
	frames, err := loadFrames(journal)
	if err != nil {
		return tip, err
	}
	if st, err := os.Stat(journal); err == nil {
		if int(st.Size()) != expectedJournalBytes(frames) {
			if err := rewriteFrames(journal, frames); err != nil {
				return tip, err
			}
			tip.Recovered = true
		}
	}
	tip.FramesKept = len(frames)
	if len(frames) > 0 {
		last := frames[len(frames)-1]
		tip.Generation = last.Generation
		var payload map[string]any
		if err := json.Unmarshal([]byte(last.Payload), &payload); err != nil {
			return tip, err
		}
		if s, ok := payload["digest_full"].(string); ok {
			tip.DigestFull = s
		}
		if s, ok := payload["table_hash"].(string); ok {
			tip.TableHash = s
		}
		if s, ok := payload["chain_digest"].(string); ok {
			tip.ChainDigest = s
		}
		if s, ok := payload["epoch_bind"].(string); ok {
			tip.EpochBind = s
		}
		if n, ok := payload["lineage_id"].(float64); ok {
			tip.LineageID = uint64(n)
		}
		if n, ok := payload["total_bound_violations"].(float64); ok {
			tip.TotalBoundViolations = int(n)
		}
		if tip.Recovered {
			tip.LineageID++
		}
		return tip, nil
	}
	raw, err := os.ReadFile(tipJSON)
	if err != nil {
		return tip, nil
	}
	if tipMarkedStale(string(raw)) {
		return tip, nil
	}
	var o map[string]any
	if err := json.Unmarshal(raw, &o); err != nil {
		return tip, err
	}
	if n, ok := o["generation"].(float64); ok {
		tip.Generation = uint64(n)
	}
	if s, ok := o["digest_full"].(string); ok {
		tip.DigestFull = s
	}
	if s, ok := o["table_hash"].(string); ok {
		tip.TableHash = s
	}
	if s, ok := o["chain_digest"].(string); ok {
		tip.ChainDigest = s
	}
	if s, ok := o["epoch_bind"].(string); ok {
		tip.EpochBind = s
	}
	if n, ok := o["lineage_id"].(float64); ok {
		tip.LineageID = uint64(n)
	}
	if n, ok := o["total_bound_violations"].(float64); ok {
		tip.TotalBoundViolations = int(n)
	}
	_ = bindPath
	return tip, nil
}

func tipMarkedStale(raw string) bool {
	return contains(raw, `"stale": true`) || contains(raw, `"stale":true`)
}

func contains(s, sub string) bool {
	return len(s) >= len(sub) && (s == sub || len(sub) == 0 || indexOf(s, sub) >= 0)
}

func indexOf(s, sub string) int {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return i
		}
	}
	return -1
}

func writeHeadJSON(tipJSON string, tip HeadState) error {
	obj := map[string]any{
		"stale":                  false,
		"generation":             tip.Generation,
		"lineage_id":             tip.LineageID,
		"digest_full":            tip.DigestFull,
		"table_hash":             tip.TableHash,
		"chain_digest":           tip.ChainDigest,
		"epoch_bind":             tip.EpochBind,
		"total_bound_violations": tip.TotalBoundViolations,
		"frames_kept":            tip.FramesKept,
		"resumed":                false,
	}
	body, err := json.MarshalIndent(obj, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(tipJSON), 0o755); err != nil {
		return err
	}
	return os.WriteFile(tipJSON, append(body, '\n'), 0o644)
}

func writeEpochBind(path string, tip HeadState) error {
	obj := map[string]any{
		"epoch_bind": tip.EpochBind,
		"table_hash": tip.TableHash,
		"lineage_id": tip.LineageID,
	}
	body, err := json.MarshalIndent(obj, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(body, '\n'), 0o644)
}

func loadEpochBind(path string) (epochBind, tableHash string, lineageID uint64, ok bool) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return "", "", 0, false
	}
	var o map[string]any
	if err := json.Unmarshal(raw, &o); err != nil {
		return "", "", 0, false
	}
	s1, _ := o["epoch_bind"].(string)
	s2, _ := o["table_hash"].(string)
	var lid uint64
	if n, ok := o["lineage_id"].(float64); ok {
		lid = uint64(n)
	}
	if len(s1) != 64 || len(s2) != 64 {
		return "", "", 0, false
	}
	return s1, s2, lid, true
}
