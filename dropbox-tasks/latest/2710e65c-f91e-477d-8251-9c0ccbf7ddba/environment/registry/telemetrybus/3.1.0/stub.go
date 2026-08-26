package telemetrybus

import (
	"context"
	"errors"
	"fmt"
)

// MaxFrameBytes is the largest single event frame the bus accepts.
const MaxFrameBytes = 96

// WindowCapacity is the number of frames one reporting window delivers
// before it is full. A window that has delivered this many frames accepts
// no more.
const WindowCapacity = 4

// ErrWindowFull is what Queue reports once the window it belongs to has
// already delivered WindowCapacity frames. The window buffers and delivers
// nothing further; the pending batch is left exactly as it was.
var ErrWindowFull = errors.New("telemetrybus: window has reached its delivery capacity")

// MaxWindowsPerProcess is the number of reporting windows a single process
// may open over its life. Open and OpenAt both draw from this same budget,
// and closing a window does not return its share.
const MaxWindowsPerProcess = 2

// ErrTooManyWindows is what Open and OpenAt report once a process has
// already opened MaxWindowsPerProcess windows.
var ErrTooManyWindows = errors.New("telemetrybus: process has already opened its window budget")

// windowsOpened is the process-wide count of windows opened so far via
// Open or OpenAt.
var windowsOpened int

// Record is one frame the bus accepted, paired with the slot the
// delivering window stamped it with.
type Record struct {
	Slot  int
	Event string
}

// deliveries is the bus's process-wide record of accepted frames, in the
// order they reached the bus.
var deliveries []Record

// Delivered returns the bus's delivery record for this process: every
// accepted frame in order, each with the slot it carried.
func Delivered() []Record {
	out := make([]Record, len(deliveries))
	copy(out, deliveries)
	return out
}

// Window is a reporting window opened by Open or OpenAt. A window stamps
// the frames it delivers with consecutive slots starting from the slot it
// was opened at, and delivers at most WindowCapacity frames before it is
// full.
type Window struct {
	next      int // the slot the next delivered frame will carry
	delivered int // frames this window has delivered so far
	pending   []string
}

// Open starts a reporting window whose delivery run begins at slot 0. It
// reports ErrTooManyWindows instead once the process has already opened
// MaxWindowsPerProcess windows.
func Open() (*Window, error) {
	if windowsOpened >= MaxWindowsPerProcess {
		return nil, ErrTooManyWindows
	}
	windowsOpened++
	return &Window{}, nil
}

// OpenAt starts a reporting window whose delivery run begins at slot
// instead of at 0. It reports ErrTooManyWindows instead once the process
// has already opened MaxWindowsPerProcess windows.
func OpenAt(slot int) (*Window, error) {
	if windowsOpened >= MaxWindowsPerProcess {
		return nil, ErrTooManyWindows
	}
	windowsOpened++
	return &Window{next: slot}, nil
}

// Queue buffers event for the next Flush. It reports an error immediately,
// before any delivery activity, when event exceeds MaxFrameBytes, and
// reports ErrWindowFull when this window has already delivered
// WindowCapacity frames; in either case the pending batch is left exactly
// as it was.
func (w *Window) Queue(event string) error {
	if len(event) > MaxFrameBytes {
		return fmt.Errorf("telemetrybus: frame of %d bytes exceeds the %d byte limit", len(event), MaxFrameBytes)
	}
	if w.delivered >= WindowCapacity {
		return ErrWindowFull
	}
	w.pending = append(w.pending, event)
	return nil
}

// Flush delivers every pending frame under ctx, stamping each with this
// window's next slot, and clears the batch. A context that is already done
// aborts before anything is marked delivered and the batch stays pending
// for the next call.
func (w *Window) Flush(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	for _, e := range w.pending {
		deliveries = append(deliveries, Record{Slot: w.next, Event: e})
		w.next++
		w.delivered++
	}
	w.pending = w.pending[:0]
	return nil
}

// Close releases the window. Calling it more than once is a no-op.
func (w *Window) Close() error {
	w.pending = nil
	return nil
}
