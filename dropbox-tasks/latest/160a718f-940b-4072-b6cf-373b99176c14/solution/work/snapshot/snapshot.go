package snapshot
import ("crypto/sha256"; "encoding/hex"; "io"; "os"; "path/filepath"; "sort"; "vaultqualify/internal/canon")
func Identity(vault string) (string, error) {
    var members []map[string]string
    for _, rel := range []string{"manifest.json", "authority/ledger.jsonl", "rewrap/journal.jsonl", "objects", "envelopes", "shares"} {
        root := filepath.Join(vault, rel)
        _ = filepath.WalkDir(root, func(p string, d os.DirEntry, err error) error {
            if err != nil || d.IsDir() { return nil }
            b, e := os.ReadFile(p); if e != nil { return e }
            members = append(members, map[string]string{"path": filepath.ToSlash(p[len(vault)+1:]), "sha256": hex.EncodeToString(sha256Sum(b))})
            return nil
        })
    }
    sort.Slice(members, func(i, j int) bool { return members[i]["path"] < members[j]["path"] })
    raw, err := canon.Marshal(members); if err != nil { return "", err }
    return hex.EncodeToString(sha256Sum(raw)), nil
}
func sha256Sum(b []byte) []byte { h := sha256.Sum256(b); return h[:] }
var _ = io.Discard
