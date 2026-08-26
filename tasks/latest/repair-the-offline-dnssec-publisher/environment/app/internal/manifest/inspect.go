package manifest

import (
	"encoding/json"
	"fmt"
	"os"
)

func Inspect(path, format string) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	var doc Document
	if err := json.Unmarshal(data, &doc); err != nil {
		return err
	}
	switch format {
	case "json":
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		return enc.Encode(doc)
	case "text":
		fmt.Printf("origin=%s epoch=%d serial=%d keys=%d\n", doc.Origin, doc.Epoch, doc.Serial, len(doc.Keys))
		for _, k := range doc.Keys {
			fmt.Printf("  %s role=%s status=%s tag=%d\n", k.LineageID, k.Role, k.Status, k.KeyTag)
		}
		return nil
	default:
		return fmt.Errorf("unknown format %s", format)
	}
}
