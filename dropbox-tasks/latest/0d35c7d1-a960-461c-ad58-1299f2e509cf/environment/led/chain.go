package led

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"

	"qxhub/pth"
)

// vex_chain appends one committed entry to the durable ledger and returns it.
func vex_chain(gen, floor, epoch int, arm, seal, tx string) (Entry, error) {
	e := Entry{
		Prev:  "0",
		Gen:   gen,
		Floor: floor,
		Epoch: epoch,
		Arm:   arm,
		Seal:  seal,
		Tx:    tx,
	}
	payload := fmt.Sprintf("%d|%s|%s|%s", e.Gen, e.Arm, e.Seal, e.Tx)
	sum := sha256.Sum256([]byte(payload))
	e.Hash = hex.EncodeToString(sum[:])
	raw, err := json.Marshal(e)
	if err != nil {
		return Entry{}, err
	}
	fh, err := os.OpenFile(pth.LedgerPath(), os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return Entry{}, err
	}
	defer fh.Close()
	if _, err := fh.Write(append(raw, '\n')); err != nil {
		return Entry{}, err
	}
	return e, nil
}

func readAll() ([]Entry, error) {
	fh, err := os.Open(pth.LedgerPath())
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	defer fh.Close()
	var out []Entry
	sc := bufio.NewScanner(fh)
	for sc.Scan() {
		line := sc.Text()
		if line == "" {
			continue
		}
		var e Entry
		if err := json.Unmarshal([]byte(line), &e); err != nil {
			continue
		}
		out = append(out, e)
	}
	return out, sc.Err()
}
