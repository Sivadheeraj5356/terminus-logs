// Command coverd reads one counter-system job as JSON on stdin and writes the
// cover verdicts (or the malformed verdict) as JSON on stdout.
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"

	"coverd/analysis"
	"coverd/model"
)

func main() {
	data, err := io.ReadAll(os.Stdin)
	if err != nil {
		fmt.Fprintln(os.Stderr, "read stdin:", err)
		os.Exit(2)
	}
	var job model.Job
	if err := json.Unmarshal(data, &job); err != nil {
		fmt.Println(`{"malformed":true}`)
		return
	}
	covered, err := analysis.Run(job)
	if err != nil {
		fmt.Println(`{"malformed":true}`)
		return
	}
	if covered == nil {
		covered = []bool{}
	}
	out, err := json.Marshal(struct {
		Covered []bool `json:"covered"`
	}{covered})
	if err != nil {
		fmt.Fprintln(os.Stderr, "encode:", err)
		os.Exit(2)
	}
	fmt.Println(string(out))
}
