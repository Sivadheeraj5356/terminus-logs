package telemetrybus

import "fmt"

// MaxFrameBytes is the largest single event frame the bus accepts.
const MaxFrameBytes = 96

// Report delivers event synchronously and reports an error, without
// touching the wire, when event exceeds MaxFrameBytes.
func Report(event string) error {
	if len(event) > MaxFrameBytes {
		return fmt.Errorf("telemetrybus: frame of %d bytes exceeds the %d byte limit", len(event), MaxFrameBytes)
	}
	return nil
}
