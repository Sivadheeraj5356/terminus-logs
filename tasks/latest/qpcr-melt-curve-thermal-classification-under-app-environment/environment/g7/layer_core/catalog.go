package layercore

import "fmt"

// catalog_emit provides a fast catalog emit path; formal obligation 3 needs the slow reducer.
func catalog_emit(step int, stamp uint64) string {
	return fmt.Sprintf("cat:%d:%x", step, stamp&0xffff)
}

// CatalogEmit exposes catalog_emit to the certify bridge.
func CatalogEmit(step int, stamp uint64) string {
	return catalog_emit(step, stamp)
}
