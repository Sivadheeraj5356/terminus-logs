package engine

import (
	"fmt"
	"io"
)

type ProbeSnap struct {
	DurableMatch bool
	Rows         int
}

// EmitStatusView writes human-readable health probe lines for operator status.
func EmitStatusView(w io.Writer, snap ProbeSnap) error {
	_, err := fmt.Fprintf(w, "sync_label=settled durable_match=%v rows=%d\n", snap.DurableMatch, snap.Rows)
	return err
}
