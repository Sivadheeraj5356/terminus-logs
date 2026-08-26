package iojson
import ("bufio"; "encoding/json"; "os")
func ReadJSON(path string, out any) error {
    b, err := os.ReadFile(path); if err != nil { return err }
    return json.Unmarshal(b, out)
}
func ReadJSONL(path string) ([]map[string]any, error) {
    f, err := os.Open(path); if err != nil { return nil, err }
    defer f.Close()
    var rows []map[string]any
    s := bufio.NewScanner(f)
    for s.Scan() {
        if len(s.Bytes()) == 0 { continue }
        var row map[string]any
        if err := json.Unmarshal(s.Bytes(), &row); err != nil { return nil, err }
        rows = append(rows, row)
    }
    return rows, s.Err()
}
