package ingest

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
)

func sha256Hex(data string) string {
	sum := sha256.Sum256([]byte(data))
	return hex.EncodeToString(sum[:])
}

func LoadRawLines(manifest Manifest, base string) ([]RawLine, error) {
	var lines []RawLine
	if len(manifest.Lanes) > 0 {
		for _, lane := range manifest.Lanes {
			path := manifest.Resolve(base, lane.Path)
			chunk, err := readRawFile(path, lane.Name, lane.Priority)
			if err != nil {
				return nil, err
			}
			lines = append(lines, chunk...)
		}
		return lines, nil
	}
	path := manifest.Resolve(base, manifest.Journal)
	return readRawFile(path, "", 0)
}

func readRawFile(path, lane string, priority int) ([]RawLine, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	var lines []RawLine
	sc := bufio.NewScanner(f)
	lineNum := 0
	for sc.Scan() {
		line := sc.Text()
		if line == "" {
			continue
		}
		lines = append(lines, RawLine{
			Lane:     lane,
			Priority: priority,
			LineNum:  lineNum,
			Raw:      line,
			RawHash:  sha256Hex(line),
		})
		lineNum++
	}
	if err := sc.Err(); err != nil {
		return nil, err
	}
	return lines, nil
}

func ParseEvent(raw RawLine, defaultSource string) (Record, error) {
	var obj map[string]interface{}
	if err := json.Unmarshal([]byte(raw.Raw), &obj); err != nil {
		return Record{}, err
	}
	for _, req := range []string{"seq", "epoch", "kind"} {
		if _, ok := obj[req]; !ok {
			return Record{}, fmt.Errorf("missing field %s", req)
		}
	}
	epoch, err := asInt(obj["epoch"])
	if err != nil {
		return Record{}, err
	}
	seq, err := asInt(obj["seq"])
	if err != nil {
		return Record{}, err
	}
	if epoch < 0 || seq < 0 {
		return Record{}, fmt.Errorf("negative epoch or seq")
	}
	kind, _ := obj["kind"].(string)
	source := defaultSource
	if v, ok := obj["source"].(string); ok {
		source = v
	}
	rev := 0
	if v, ok := obj["rev"]; ok {
		rev, err = asInt(v)
		if err != nil {
			return Record{}, err
		}
	}
	cancel := false
	if v, ok := obj["cancel"].(bool); ok {
		cancel = v
	}
	opID := fmt.Sprintf("%d:%d:%s:%s", epoch, seq, source, raw.Lane)
	if v, ok := obj["op_id"].(string); ok {
		opID = v
	}
	rec := Record{
		Raw:    raw,
		Epoch:  epoch,
		Seq:    seq,
		Kind:   kind,
		Source: source,
		Rev:    rev,
		Cancel: cancel,
		OpID:   opID,
	}
	linkKinds := map[string]bool{
		"link_open": true, "link_close": true, "hop": true,
		"quarantine": true, "clear_quarantine": true,
	}
	if linkKinds[kind] {
		link, ok := obj["link"].(string)
		if !ok || link == "" {
			return Record{}, fmt.Errorf("missing link")
		}
		rec.Link = link
	}
	if kind == "hop" {
		ms, err := asInt(obj["ms"])
		if err != nil {
			return Record{}, err
		}
		if ms < 0 {
			return Record{}, fmt.Errorf("negative latency")
		}
		rec.Ms = ms
	}
	if kind == "checkpoint" {
		tag, _ := obj["tag"].(string)
		if tag == "" {
			return Record{}, fmt.Errorf("empty checkpoint tag")
		}
		rec.Tag = tag
	}
	if kind == "policy_update" {
		pol, ok := obj["policy"].(map[string]interface{})
		if !ok {
			return Record{}, fmt.Errorf("invalid policy update")
		}
		rec.Policy = pol
	}
	if kindRank(kind) == 99 {
		return Record{}, fmt.Errorf("unknown kind %s", kind)
	}
	return rec, nil
}

func asInt(v interface{}) (int, error) {
	switch n := v.(type) {
	case float64:
		return int(n), nil
	case json.Number:
		i, err := n.Int64()
		return int(i), err
	case int:
		return n, nil
	default:
		return 0, fmt.Errorf("not an integer")
	}
}
