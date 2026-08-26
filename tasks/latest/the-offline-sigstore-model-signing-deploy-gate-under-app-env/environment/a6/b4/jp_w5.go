package b4

import "fmt"

// JpW5 is a decoy pretty-printer for scratch dumps (not on the gate path).
func JpW5(scratch string) string {
	return fmt.Sprintf("dump:%s", scratch)
}
