package main

import "fmt"

// SocialContribution returns the employer social contribution in integer
// micro-units for an employee whose gross is `gross`, working in the given
// statutory region and country. It uses the region rule in SocialParams and the
// country floor in CountryFloor (see docs/spec.md for how the floor and cap
// combine).
//
// Stub: the real computation is supplied by the solution.
func SocialContribution(gross int64, region, country string) (int64, error) {
	_, _, _ = gross, region, country
	return 0, fmt.Errorf("not_implemented")
}
