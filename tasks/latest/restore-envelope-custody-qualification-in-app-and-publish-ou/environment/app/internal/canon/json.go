package canon
import ("bytes"; "encoding/json"; "sort")
func Marshal(v any) ([]byte, error) {
    switch t := v.(type) {
    case map[string]any:
        return marshalMap(t)
    default:
        raw, err := json.Marshal(v); if err != nil { return nil, err }
        var generic any
        if err := json.Unmarshal(raw, &generic); err != nil { return raw, nil }
        if m, ok := generic.(map[string]any); ok { return marshalMap(m) }
        return raw, nil
    }
}
func marshalMap(m map[string]any) ([]byte, error) {
    keys := make([]string, 0, len(m)); for k := range m { keys = append(keys, k) }; sort.Strings(keys)
    var buf bytes.Buffer; buf.WriteByte('{')
    for i, k := range keys {
        if i > 0 { buf.WriteByte(',') }
        kb, _ := json.Marshal(k); buf.Write(kb); buf.WriteByte(':')
        vb, err := marshalValue(m[k]); if err != nil { return nil, err }; buf.Write(vb)
    }
    buf.WriteByte('}'); return buf.Bytes(), nil
}
func marshalValue(v any) ([]byte, error) {
    switch t := v.(type) {
    case map[string]any:
        return marshalMap(t)
    case []any:
        var buf bytes.Buffer; buf.WriteByte('[')
        for i, item := range t {
            if i > 0 { buf.WriteByte(',') }
            b, err := marshalValue(item); if err != nil { return nil, err }; buf.Write(b)
        }
        buf.WriteByte(']'); return buf.Bytes(), nil
    case []string:
        items := make([]any, len(t)); for i, s := range t { items[i] = s }
        return marshalValue(items)
    default:
        return json.Marshal(v)
    }
}
