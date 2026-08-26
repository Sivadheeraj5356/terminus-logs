package journalspan

import "fmt"

// ScanSpanMix compares two span_mix values for a fixture label.
// Used by offline diagnostics only; does not mutate ledger state.
func ScanSpanMix(label, left, right string) error {
	if left == right {
		return nil
	}
	return fmt.Errorf("span mix drift for %s", label)
}
