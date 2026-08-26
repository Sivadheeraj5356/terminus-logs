package journal
func Newest(records []map[string]any) (string, error) {
    var best map[string]any
    for _, rec := range records {
        if best == nil || int(rec["sequence"].(float64)) > int(best["sequence"].(float64)) { best = rec }
    }
    if best == nil { return "", nil }
    if id, ok := best["transaction_id"].(string); ok { return id, nil }
    return "", nil
}
