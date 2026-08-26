package journal
func ResolveHead(records []map[string]any) (string, error) {
    var newest map[string]any
    for _, rec := range records {
        if newest == nil || int(rec["sequence"].(float64)) > int(newest["sequence"].(float64)) {
            newest = rec
        }
    }
    if newest == nil { return "", nil }
    if newest["kind"] == "rollback" {
        if p, ok := newest["parent_transaction_id"].(string); ok { return p, nil }
    }
    if id, ok := newest["transaction_id"].(string); ok { return id, nil }
    return "", nil
}
