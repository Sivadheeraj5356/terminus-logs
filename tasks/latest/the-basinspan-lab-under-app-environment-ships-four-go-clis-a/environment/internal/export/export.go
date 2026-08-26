package export

import (
    "encoding/csv"
    "encoding/json"
    "fmt"
    "os"
    "os/exec"
    "sort"
    "strings"

    "bs7/internal/paths"
)

type ProfileResult struct {
    Label           string    `json:"label"`
    PairID          string    `json:"pair_id"`
    Accepted        bool      `json:"accepted"`
    PairDigestHex   string    `json:"pair_digest_hex"`
    MergeDigestHex  string    `json:"merge_digest_hex"`
    AlignCost       float64   `json:"align_cost"`
    EvalMSE         float64   `json:"eval_mse"`
    NaiveMSE        float64   `json:"naive_mse"`
    BarrierValue    float64   `json:"barrier_value"`
    Permutations    [][]int   `json:"permutations"`
}

type Report struct {
    Generation      int             `json:"generation"`
    PolicyEpoch     int             `json:"policy_epoch"`
    ReportDigestHex string          `json:"report_digest_hex"`
    Profiles        []ProfileResult `json:"profiles"`
}

type TraceRow struct {
    Label          string  `json:"label"`
    Layer          int     `json:"layer"`
    NeuronA        int     `json:"neuron_a"`
    NeuronB        int     `json:"neuron_b"`
    Correlation    float64 `json:"correlation"`
    AssignmentCost float64 `json:"assignment_cost"`
}

type JournalLine struct {
    Label        string  `json:"label"`
    EvalMSE      float64 `json:"eval_mse"`
    BarrierValue float64 `json:"barrier_value"`
    AlignCost    float64 `json:"align_cost"`
}

type Certificate struct {
    Label         string  `json:"label"`
    PairID        string  `json:"pair_id"`
    EvalMSE       float64 `json:"eval_mse"`
    BarrierValue  float64 `json:"barrier_value"`
    Permutations  [][]int `json:"permutations"`
    CertDigestHex string  `json:"cert_digest_hex"`
}

func runSha(line string) string {
    cmd := exec.Command("python3", paths.Root()+"/tools/parity_sha.py", "hex", line)
    out, err := cmd.Output()
    if err != nil {
        return ""
    }
    return strings.TrimSpace(string(out))
}

func ReportDigest(gen, epoch int, digests []string) string {
    sort.Strings(digests)
    line := fmt.Sprintf("gen=%d|epoch=%d|digests=%s", gen, epoch, strings.Join(digests, ","))
    return runSha(line)
}

func CertDigest(label string, barrier, evalMSE float64, perms [][]int) string {
    parts := make([]string, 0, len(perms))
    for _, p := range perms {
        ss := make([]string, len(p))
        for i, v := range p {
            ss[i] = fmt.Sprintf("%d", v)
        }
        parts = append(parts, strings.Join(ss, ","))
    }
    flat := strings.Join(parts, ";")
    line := fmt.Sprintf("label=%s|barrier=%.6f|mse=%.6f|perms=%s", label, barrier, evalMSE, flat)
    return runSha(line)
}

func WriteReport(r Report) error {
    b, err := json.MarshalIndent(r, "", "  ")
    if err != nil {
        return err
    }
    return os.WriteFile(paths.OutputDir()+"/merge_report.json", b, 0644)
}

func WriteTrace(rows []TraceRow) error {
    f, err := os.Create(paths.OutputDir() + "/alignment_trace.csv")
    if err != nil {
        return err
    }
    defer f.Close()
    w := csv.NewWriter(f)
    _ = w.Write([]string{"label", "layer", "neuron_a", "neuron_b", "correlation", "assignment_cost"})
    for _, r := range rows {
        _ = w.Write([]string{
            r.Label,
            fmt.Sprintf("%d", r.Layer),
            fmt.Sprintf("%d", r.NeuronA),
            fmt.Sprintf("%d", r.NeuronB),
            fmt.Sprintf("%g", r.Correlation),
            fmt.Sprintf("%g", r.AssignmentCost),
        })
    }
    w.Flush()
    return w.Error()
}

func WriteJournal(lines []JournalLine) error {
    f, err := os.Create(paths.OutputDir() + "/merge_journal.jsonl")
    if err != nil {
        return err
    }
    defer f.Close()
    for _, ln := range lines {
        b, _ := json.Marshal(ln)
        if _, err := f.Write(append(b, '\n')); err != nil {
            return err
        }
    }
    return nil
}

func WriteCertificate(c Certificate) error {
    b, err := json.MarshalIndent(c, "", "  ")
    if err != nil {
        return err
    }
    return os.WriteFile(paths.OutputDir()+"/barrier_certificate.json", b, 0644)
}
