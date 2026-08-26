// Writes the compat/telemetrybusv1 adapter (R7) for whichever telemetrybus
// version /app/out/lock.json resolves. This is a separate program from
// resolver/main.go: R7's compat package is free-form by contract and is
// not part of R11's runnable-resolver check, so writing it never runs
// through the same argv-driven, rerun-against-unseen-input path resolver
// gets tested against.
//
// SHIM WINDOW (R7): telemetrybus 3.1.0 delivers slot-addressed. A window
// opened with Open numbers its deliveries from 0, a window goes full after
// WindowCapacity deliveries and then reports ErrWindowFull, OpenAt(slot)
// starts a window's run at slot, and a process's deliveries are meant to
// form one continuous slot run (registry/telemetrybus/3.1.0/MIGRATION.md).
// consumer.go reports once, so several adapters look correct on a single-
// call smoke test yet break the continuous run under a multi-call load. A
// per-call Open/Queue/Flush/Close adapter reopens a fresh window each call,
// restarts the slot at 0, and stamps every delivery 0. An adapter that
// keeps one window and reuses it is continuous only until that window
// fills: the WindowCapacity+1 delivery gets ErrWindowFull and the error
// surfaces to the caller, since consumer.go's one report never reaches the
// cap for the model to notice. A third shape passes both of those checks
// without ever reusing anything: a package-level slot counter plus
// OpenAt(counter) on every call opens a fresh window each time but hands it
// the correct starting slot, so the run stays continuous by construction
// and the window never accumulates enough deliveries to hit
// WindowCapacity. MaxWindowsPerProcess closes that gap by capping how many
// windows a process may open at all, independent of how full any one of
// them gets, so only an adapter that actually batches deliveries into a
// window before rolling over survives. The reference adapter below
// (adapterNewTemplate) reuses one window and, when it fills, carries the
// run forward in a window opened at the process's next slot, so the slots
// stay 0,1,2,3,... unbroken across exactly as many windows as
// MaxWindowsPerProcess allows. This is a cross-call state cold: it does not
// come from reading stub.go's surface alone, it comes from reasoning about
// how the single-Report v1 facade must map onto a stateful, capacity- and
// window-bounded v3 window, and it is orthogonal to the graph and caret
// colds resolver/main.go carries.
//
// Build: go build -o /tmp/writeadapter /solution/writeadapter.go
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

type version struct {
	major, minor, patch int
}

func parseVersion(s string) (version, error) {
	parts := strings.Split(s, ".")
	if len(parts) != 3 {
		return version{}, fmt.Errorf("bad version %q", s)
	}
	nums := make([]int, 3)
	for i, p := range parts {
		n, err := strconv.Atoi(p)
		if err != nil {
			return version{}, fmt.Errorf("bad version %q: %w", s, err)
		}
		nums[i] = n
	}
	return version{nums[0], nums[1], nums[2]}, nil
}

const adapterOldTemplate = `package telemetrybusv1

import "fleetmesh/telemetrybus"

// Report preserves the pre-migration contract consumer.go relies on: one
// call delivers event synchronously and reports whatever error the resolved
// telemetrybus release surfaces.
func Report(event string) error {
	return telemetrybus.Report(event)
}
`

const adapterNewTemplate = `package telemetrybusv1

import (
	"context"
	"errors"

	"fleetmesh/telemetrybus"
)

// window is the reporting window this compat layer currently delivers
// through. telemetrybus 3.1.0 stamps each delivery with the next slot in
// the window's run, a window opened with Open begins that run at 0, and a
// process's deliveries are meant to form one continuous slot run (see
// registry/telemetrybus/3.1.0/MIGRATION.md). Report keeps one window and
// reuses it so the run stays continuous. A window goes full after
// telemetrybus.WindowCapacity deliveries and then reports ErrWindowFull, so
// Report carries the run forward into a window opened at the process's next
// slot rather than restarting at 0 or surfacing the full-window error to
// the caller.
var window *telemetrybus.Window

func ensureWindow() (*telemetrybus.Window, error) {
	if window == nil {
		w, err := telemetrybus.Open()
		if err != nil {
			return nil, err
		}
		window = w
	}
	return window, nil
}

// Report preserves the pre-migration contract consumer.go relies on: one
// call queues and delivers event synchronously and reports whichever step
// failed. Flush runs under context.Background so a plain call site that
// never had a context to pass keeps working exactly as before. When the
// current window has filled, Report opens a continuation window at the
// process's next delivery slot and retries the event there, so the slot run
// stays continuous across the window boundary.
func Report(event string) error {
	w, err := ensureWindow()
	if err != nil {
		return err
	}
	err = w.Queue(event)
	if errors.Is(err, telemetrybus.ErrWindowFull) {
		w, err = telemetrybus.OpenAt(len(telemetrybus.Delivered()))
		if err != nil {
			return err
		}
		window = w
		err = w.Queue(event)
	}
	if err != nil {
		return err
	}
	return w.Flush(context.Background())
}
`

// writeAdapter emits the compat package for whichever telemetrybus version
// the resolution settled on. telemetrybus versions at or above 3.1.0 in
// this registry ship the Open/Queue/Flush surface instead of Report
// directly (see registry/telemetrybus/3.1.0/MIGRATION.md); everything
// below still exposes Report directly.
func writeAdapter(dir string, telemetrybusVersion version) error {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	body := adapterOldTemplate
	if telemetrybusVersion.major >= 3 {
		body = adapterNewTemplate
	}
	return os.WriteFile(filepath.Join(dir, "adapter.go"), []byte(body), 0o644)
}

// ---------- main ----------

func main() {
	lockPath := "/app/out/lock.json"
	compatDir := "/app/project/compat/telemetrybusv1"

	raw, err := os.ReadFile(lockPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "read lock:", err)
		os.Exit(1)
	}
	var lock map[string]string
	if err := json.Unmarshal(raw, &lock); err != nil {
		fmt.Fprintln(os.Stderr, "parse lock:", err)
		os.Exit(1)
	}
	telemetrybusVerStr, ok := lock["telemetrybus"]
	if !ok {
		fmt.Fprintln(os.Stderr, "resolution never reached telemetrybus")
		os.Exit(1)
	}
	telemetrybusVer, err := parseVersion(telemetrybusVerStr)
	if err != nil {
		fmt.Fprintln(os.Stderr, "parse telemetrybus version:", err)
		os.Exit(1)
	}
	if err := writeAdapter(compatDir, telemetrybusVer); err != nil {
		fmt.Fprintln(os.Stderr, "write adapter:", err)
		os.Exit(1)
	}
}
