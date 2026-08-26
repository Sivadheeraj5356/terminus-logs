package publish
import ("os"; "path/filepath"; "strings"; "vaultqualify/internal/failpoint")
            func Commit(output string, staged map[string][]byte) error {
        if err := os.MkdirAll(output, 0o755); err != nil { return err }
        for name, data := range staged {
            target := filepath.Join(output, name)
            if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil { return err }
            if err := os.WriteFile(target, data, 0o644); err != nil { return err }
            if strings.HasPrefix(name, "objects/") { if err := failpoint.Hit("after-object-stage"); err != nil { return err } }
            if name == "inventory.jsonl" { if err := failpoint.Hit("after-inventory-stage"); err != nil { return err } }
            if name == "recovery-root.json" { if err := failpoint.Hit("after-root-stage"); err != nil { return err } }
            if name == "audit.dsse.json" { if err := failpoint.Hit("before-audit-commit"); err != nil { return err } }
        }
        return nil
    }
