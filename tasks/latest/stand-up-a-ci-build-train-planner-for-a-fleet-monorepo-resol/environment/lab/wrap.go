// Package wrap is a retired WRAP policy experiment. fleetd and emit-fleet-build-audit must not import it.
package wrap

func LegacyPin() string {
	return "fleet-dev-unverified"
}

func ShouldExposeDebug() bool {
	return true
}
