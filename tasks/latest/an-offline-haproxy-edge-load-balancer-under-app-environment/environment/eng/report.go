package eng

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"

	"qxhub/gst"
	"qxhub/led"
	"qxhub/zeb"
)

func ledHead() (string, bool, error) {
	h, ok, err := led.Head()
	if err != nil || !ok {
		return "", ok, err
	}
	return h.Hash, true, nil
}

// Status reports the live session counters and durable pointers as JSON.
func Status() (map[string]any, error) {
	sess, err := zeb.Load()
	if err != nil {
		return nil, err
	}
	head := ""
	if h, ok, err := led.Head(); err == nil && ok {
		head = h.Hash
	}
	return map[string]any{
		"active_gen":  sess.ActiveGen,
		"floor":       sess.Floor,
		"epoch":       sess.Epoch,
		"anchor":      sess.Anchor,
		"last_arm":    sess.LastArm,
		"current":     gst.ReadCurrent(),
		"ledger_head": head,
	}, nil
}

// Verify recomputes the ledger chain, checks the current pointer against the
// ledger head, and validates the registry anchor formula.
func Verify() (map[string]any, error) {
	sess, err := zeb.Load()
	if err != nil {
		return nil, err
	}
	ents, err := led.ReplayAll()
	if err != nil {
		return nil, err
	}
	ok := true
	msg := "ok"
	prev := "0"
	for _, e := range ents {
		if e.Prev != prev {
			ok = false
			msg = "ledger chain break"
			break
		}
		payload := fmt.Sprintf("%s|%d|%s|%s|%s", e.Prev, e.Gen, e.Arm, e.Seal, e.Tx)
		sum := sha256.Sum256([]byte(payload))
		if hex.EncodeToString(sum[:]) != e.Hash {
			ok = false
			msg = "ledger entry hash mismatch"
			break
		}
		prev = e.Hash
	}
	cur := gst.ReadCurrent()
	if ok && cur > 0 && len(ents) > 0 && ents[len(ents)-1].Gen != cur {
		ok = false
		msg = "current/ledger gen mismatch"
	}
	if ok && sess.Anchor != zeb.SealAnchor(sess.ActiveGen, sess.Floor, sess.Epoch) {
		ok = false
		msg = "registry anchor mismatch"
	}
	return map[string]any{
		"ok":             ok,
		"message":        msg,
		"active_gen":     sess.ActiveGen,
		"floor":          sess.Floor,
		"epoch":          sess.Epoch,
		"current":        cur,
		"ledger_entries": len(ents),
	}, nil
}

// RecoverCorrupt falls back to the last valid generation and reports it.
func RecoverCorrupt() (int, string, error) {
	if err := led.Mend(); err != nil {
		return 0, "", err
	}
	return gst.FallbackValid()
}

// PrintJSON writes one JSON document to stdout.
func PrintJSON(doc map[string]any) error {
	raw, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	_, err = os.Stdout.Write(append(raw, '\n'))
	return err
}
