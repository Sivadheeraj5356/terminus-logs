package main

import (
	"fmt"
	"os"

	"fleetmesh/compat/telemetrybusv1"
)

// notifyStartup reports a single startup event through the compat layer
// and returns whatever error the call surfaces.
func notifyStartup() error {
	return telemetrybusv1.Report("svc.startup ok")
}

func main() {
	if err := notifyStartup(); err != nil {
		fmt.Fprintln(os.Stderr, "notify:", err)
		os.Exit(1)
	}
	fmt.Println("notify-ok")
}
