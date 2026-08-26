package main

import (
	"encoding/json"
	"os"
)

func main() {
	var in struct {
		Blob string `json:"blob"`
	}
	if err := json.NewDecoder(os.Stdin).Decode(&in); err != nil {
		os.Exit(1)
	}
	json.NewEncoder(os.Stdout).Encode(map[string]interface{}{"results": []interface{}{}})
}
