package layercore

import "fmt"

func FormatLaneLine(step int, stamp uint64) string {
	return fmt.Sprintf("step=%d stamp=%016x", step, stamp)
}
