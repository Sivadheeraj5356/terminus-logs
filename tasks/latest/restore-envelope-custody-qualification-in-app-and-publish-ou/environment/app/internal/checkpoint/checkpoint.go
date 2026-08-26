package checkpoint
import ("encoding/json"; "os"; "path/filepath")
type State struct { Snapshot string `json:"evidence_snapshot_sha256"`; Complete bool `json:"complete"` }
func vaultPath(vault string) string { return filepath.Join(vault, "state", "qualification-checkpoint.json") }
func runtimePath(output string) string { return filepath.Join(filepath.Dir(output), ".vault-qualify-state", "qualification-checkpoint.json") }
func Load(vault, output, snapshot string) (State, bool, error) {
    for _, path := range []string{vaultPath(vault), runtimePath(output)} {
        b, err := os.ReadFile(path); if os.IsNotExist(err) { continue }
        if err != nil { return State{}, false, err }
        var c State; if err := json.Unmarshal(b, &c); err != nil { return State{}, false, err }
        if c.Snapshot != "" { return c, true, nil }
    }
    return State{Snapshot: snapshot}, false, nil
}
func Save(output string, c State) error {
    path := runtimePath(output)
    if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil { return err }
    b, err := json.Marshal(c); if err != nil { return err }
    return os.WriteFile(path, append(b, '\n'), 0o600)
}
