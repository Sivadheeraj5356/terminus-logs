package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"local/ovws/lib"
)

type Case struct {
	UnitID string `json:"unit_id"`
	Query  string `json:"query"`
	URI    string `json:"uri"`
	Alg    string `json:"alg"`
}

type Row struct {
	UnitID    string `json:"unit_id"`
	Arm       string `json:"arm"`
	SelID     string `json:"sel_id"`
	FetchSeq  []int  `json:"fetch_seq"`
	Scheme    string `json:"scheme"`
	URIScheme string `json:"uri_scheme"`
	Digest    string `json:"digest"`
	Status    string `json:"status"`
}

func uriOnly(uri string) string {
	switch {
	case strings.HasPrefix(uri, "prv:"):
		return "prv"
	case strings.HasPrefix(uri, "file:"):
		return "file"
	default:
		return "eng"
	}
}

func loadCases() ([]Case, error) {
	raw, err := os.ReadFile(lib.IdxPath())
	if err != nil {
		return nil, err
	}
	var names []string
	if err := json.Unmarshal(raw, &names); err != nil {
		return nil, err
	}
	var out []Case
	for _, name := range names {
		b, err := os.ReadFile(filepath.Join(lib.CaseDir(), name))
		if err != nil {
			return nil, err
		}
		var c Case
		if err := json.Unmarshal(b, &c); err != nil {
			return nil, err
		}
		out = append(out, c)
	}
	return out, nil
}

func buildRow(c Case, arm string, epoch, cycle, weight int) (Row, error) {
	sel, err := stepSelect(c.Query, arm)
	if err != nil {
		return Row{}, err
	}
	seq, err := stepOrder(c.Alg)
	if err != nil || len(seq) < 1 {
		return Row{}, fmt.Errorf("ord")
	}
	scheme, err := stepScheme(c.URI, sel)
	if err != nil {
		return Row{}, err
	}
	uriSch := uriOnly(c.URI)

	if err := stepGuard(); err != nil {
		return Row{}, err
	}

	seqParts := make([]string, len(seq))
	for i, v := range seq {
		seqParts[i] = strconv.Itoa(v)
	}
	canon := strings.Join([]string{
		c.UnitID,
		arm,
		sel,
		strings.Join(seqParts, ","),
		scheme,
		strconv.Itoa(epoch),
		strconv.Itoa(cycle),
		strconv.Itoa(weight),
	}, "|")
	if res := stepResidue(); res != "" {
		canon = canon + "|" + strings.TrimSpace(res)
	}
	digest := lib.HexSHA256([]byte(canon))

	status := "WIT_FRESH"
	if scheme == "eng" && strings.HasPrefix(c.URI, "prv:") {
		status = "SCHEME_LEGACY"
	} else if len(seq) >= 3 && seq[0] == 2 && seq[1] == 1 && seq[2] == 0 {
		status = "ORD_GAP"
	} else if strings.Contains(c.Query, "strict") && arm == "arm_a" && sel == "def" {
		status = "SEL_DRIFT"
	}

	return Row{
		UnitID:    c.UnitID,
		Arm:       arm,
		SelID:     sel,
		FetchSeq:  seq,
		Scheme:    scheme,
		URIScheme: uriSch,
		Digest:    digest,
		Status:    status,
	}, nil
}

func writeJSON(path string, v any) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(path, b, 0o644)
}

func gradeRows(traceOut string) error {
	epoch := stepEpoch()
	cycle := stepCycle()
	weight := lib.SlotWeight()
	_ = os.Setenv("OV_EPOCH", strconv.Itoa(epoch))
	_ = os.Setenv("OV_CYCLE", strconv.Itoa(cycle))

	cases, err := loadCases()
	if err != nil {
		return err
	}
	arms := []string{"arm_a", "arm_b"}
	var rows []Row
	for _, c := range cases {
		for _, arm := range arms {
			r, err := buildRow(c, arm, epoch, cycle, weight)
			if err != nil {
				return err
			}
			if err := stepNote(r.Digest[:16]); err != nil {
				return err
			}
			rows = append(rows, r)
		}
	}
	if err := stepFinalize(); err != nil {
		return err
	}
	if err := writeJSON(traceOut, rows); err != nil {
		return err
	}
	fmt.Println("SUITE_DONE")
	return nil
}

func runAll(traceOut string) error {
	_ = os.MkdirAll("/app/output", 0o755)
	_ = os.MkdirAll("/app/output/.ov_persist", 0o755)
	if err := stepPrepare(); err != nil {
		return err
	}
	return gradeRows(traceOut)
}

func runPrepareOnly() error {
	_ = os.MkdirAll("/app/output", 0o755)
	_ = os.MkdirAll("/app/output/.ov_persist", 0o755)
	return stepPrepare()
}

func runFinalizeOnly(traceOut string) error {
	_ = os.MkdirAll("/app/output", 0o755)
	_ = os.MkdirAll("/app/output/.ov_persist", 0o755)
	return gradeRows(traceOut)
}

func runProp() error {
	cases, err := loadCases()
	if err != nil {
		return err
	}
	type smoke struct {
		UnitID string `json:"unit_id"`
		Status string `json:"status"`
	}
	var out []smoke
	for _, c := range cases {
		out = append(out, smoke{UnitID: c.UnitID, Status: "PARTIAL_OK"})
	}
	return writeJSON("/app/output/smoke_trace.json", out)
}

func main() {
	suite := flag.String("suite", "all", "suite mode")
	traceOut := flag.String("trace-out", "/app/output/ov_trace.json", "trace path")
	flag.Parse()
	var err error
	switch *suite {
	case "all":
		err = runAll(*traceOut)
	case "rebuild":
		_ = os.Remove("/app/output/ov_trace.json")
		err = runAll("/app/output/ov_trace.json")
	case "prepare":
		err = runPrepareOnly()
	case "finalize":
		err = runFinalizeOnly(*traceOut)
	case "prop":
		err = runProp()
	default:
		err = fmt.Errorf("unknown suite %s", *suite)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
