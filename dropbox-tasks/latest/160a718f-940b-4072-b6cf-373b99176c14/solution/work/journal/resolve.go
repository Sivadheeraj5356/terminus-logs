package journal
import "fmt"
func ResolveHead(records []map[string]any) (string, error) {
    seen := map[int]bool{}
    commits := map[string]map[string]any{}
    active := ""
    for _, rec := range records {
        seq := int(rec["sequence"].(float64))
        if seen[seq] { return "", fmt.Errorf("duplicate journal sequence") }
        seen[seq] = true
        kind := rec["kind"].(string)
        tx := rec["transaction_id"].(string)
        switch kind {
        case "prepare":
            continue
        case "commit":
            parent, _ := rec["parent_transaction_id"].(string)
            if parent != "" {
                if _, ok := commits[parent]; !ok { return "", fmt.Errorf("unknown journal parent") }
            }
            if _, ok := commits[tx]; ok { return "", fmt.Errorf("conflicting journal commit") }
            commits[tx] = rec
            active = tx
        case "rollback":
            if tx != active { return "", fmt.Errorf("invalid rollback") }
            parent, _ := rec["parent_transaction_id"].(string)
            if parent == "" || commits[parent] == nil { return "", fmt.Errorf("invalid rollback") }
            active = parent
        default:
            return "", fmt.Errorf("unknown journal state")
        }
    }
    return active, nil
}
