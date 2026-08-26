package publish
import ("os"; "path/filepath"; "sort"; "strings"; "vaultqualify/internal/failpoint")
            func Commit(output string, staged map[string][]byte) error {
        parent := filepath.Dir(output)
        tmp, err := os.MkdirTemp(parent, ".recovery-set.pending-")
        if err != nil { return err }
        defer os.RemoveAll(tmp)
        if err := writeTree(tmp, staged); err != nil { return err }
        if err := failpoint.Hit("before-audit-commit"); err != nil { return err }
        old := output + ".previous"
        _ = os.RemoveAll(old)
        if _, err := os.Stat(output); err == nil {
            if err := os.Rename(output, old); err != nil { return err }
        }
        if err := os.Rename(tmp, output); err != nil { return err }
        return os.RemoveAll(old)
    }
    func writeTree(root string, staged map[string][]byte) error {
        objectKeys := make([]string, 0)
        for name := range staged { if strings.HasPrefix(name, "objects/") { objectKeys = append(objectKeys, name) } }
        sort.Strings(objectKeys)
        for _, name := range objectKeys {
            target := filepath.Join(root, name)
            if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil { return err }
            if err := os.WriteFile(target, staged[name], 0o644); err != nil { return err }
            if err := failpoint.Hit("after-object-stage"); err != nil { return err }
        }
        if data, ok := staged["inventory.jsonl"]; ok {
            if err := os.WriteFile(filepath.Join(root, "inventory.jsonl"), data, 0o644); err != nil { return err }
            if err := failpoint.Hit("after-inventory-stage"); err != nil { return err }
        }
        if data, ok := staged["recovery-root.json"]; ok {
            if err := os.WriteFile(filepath.Join(root, "recovery-root.json"), data, 0o644); err != nil { return err }
            if err := failpoint.Hit("after-root-stage"); err != nil { return err }
        }
        if data, ok := staged["audit.dsse.json"]; ok {
            return os.WriteFile(filepath.Join(root, "audit.dsse.json"), data, 0o644)
        }
        return nil
    }
