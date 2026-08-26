package layercore

import "fmt"

func Hex16(x uint64) string {
	return fmt.Sprintf("%016x", x)
}
