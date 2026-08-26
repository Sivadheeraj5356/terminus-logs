package spraydecoy

import (
	"encoding/json"
	"fmt"
	"os"
)

type Buff struct {
	ID    string `json:"id"`
	Label string `json:"label"`
}

type Catalog struct {
	Buffs []Buff `json:"buffs"`
}

func Print(path string) error {
	b, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	var c Catalog
	if err := json.Unmarshal(b, &c); err != nil {
		return err
	}
	for _, x := range c.Buffs {
		fmt.Printf("%s\t%s\n", x.ID, x.Label)
	}
	return nil
}
