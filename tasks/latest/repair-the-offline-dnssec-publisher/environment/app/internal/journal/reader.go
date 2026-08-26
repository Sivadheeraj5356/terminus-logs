package journal

import (
	"bufio"
	"os"
)

func ReadAll(path string) ([]Record, error) {
	f, err := os.Open(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	defer f.Close()
	var out []Record
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Bytes()
		if len(line) == 0 {
			continue
		}
		r, err := ParseLine(line)
		if err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, sc.Err()
}

func LastAccepted(records []Record) *Record {
	for i := len(records) - 1; i >= 0; i-- {
		if records[i].Phase == PhaseAccepted {
			return &records[i]
		}
	}
	return nil
}

func NextSequence(records []Record) int {
	if len(records) == 0 {
		return 1
	}
	return records[len(records)-1].Sequence + 1
}
