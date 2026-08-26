package inspect
import ("encoding/json"; "os"; "path/filepath"; "vaultqualify/internal/iojson"; "vaultqualify/internal/journal")
func Heads(vault string) (map[string]string, error) {
    records, err := iojson.ReadJSONL(filepath.Join(vault, "rewrap", "journal.jsonl")); if err != nil && !os.IsNotExist(err) { return nil, err }
    byObject := map[string][]map[string]any{}
    for _, rec := range records { oid := rec["object_id"].(string); byObject[oid] = append(byObject[oid], rec) }
    out := map[string]string{}
    for oid, group := range byObject {
        head, err := journal.ResolveHead(group); if err != nil { return nil, err }; if head != "" { out[oid] = head }
    }
    return out, nil
}
func Print(vault string) error {
    heads, err := Heads(vault); if err != nil { return err }
    return json.NewEncoder(os.Stdout).Encode(map[string]any{"heads": heads})
}
