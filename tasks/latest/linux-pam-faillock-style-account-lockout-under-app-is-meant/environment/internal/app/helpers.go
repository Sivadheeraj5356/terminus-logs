package app

import "baylock/internal/domain"

func PrimeRuntime(rt *domain.Runtime) {
	if rt.ActiveView == "" {
		rt.ActiveView = domain.ViewHost
	}
}
