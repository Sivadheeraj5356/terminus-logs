package decoys_j8

import "fmt"

func LaneRoute(endpoint string, mode int) string {
	return fmt.Sprintf("%s?m=%d", endpoint, mode)
}
