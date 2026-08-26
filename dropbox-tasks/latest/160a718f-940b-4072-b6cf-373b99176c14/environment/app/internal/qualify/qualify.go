package qualify
import (
    "fmt"
    "path/filepath"
    "sort"
    "vaultqualify/internal/audit"
    "vaultqualify/internal/canon"
    "vaultqualify/internal/checkpoint"
    "vaultqualify/internal/crypto"
    "vaultqualify/internal/inspect"
    "vaultqualify/internal/iojson"
    "vaultqualify/internal/model"
    "vaultqualify/internal/publish"
    "vaultqualify/internal/recovery"
    "vaultqualify/internal/snapshot"
)
func Run(vault, output string, epoch int) error {
    var manifest model.Manifest
    if err := iojson.ReadJSON(filepath.Join(vault, "manifest.json"), &manifest); err != nil { return err }
    if epoch == 0 { epoch = manifest.QualificationEpoch }
    snap, err := snapshot.Identity(vault); if err != nil { return err }
    cp, ok, err := checkpoint.Load(vault, output, snap); if err != nil { return err }
    if !ok { cp = checkpoint.State{Snapshot: snap, Complete: false} }
    ledger, err := iojson.ReadJSONL(filepath.Join(vault, "authority", "ledger.jsonl")); if err != nil { return err }
    heads, err := inspect.Heads(vault); if err != nil { return err }
    var rows []map[string]any
    plaintexts := map[string][]byte{}
    digests := []string{}
    for _, item := range manifest.Objects {
        var env model.Envelope
        if err := iojson.ReadJSON(filepath.Join(vault, "envelopes", item.ObjectID+".json"), &env); err != nil { return err }
        if env.CustodyEpoch > epoch { continue }
        head, ok := heads[item.ObjectID]; if !ok || head == "" { continue }
        if env.ActiveWrapID != head { return fmt.Errorf("envelope and committed head disagree") }
        shares, err := iojson.ReadJSONL(filepath.Join(vault, "shares", head+".jsonl")); if err != nil { return err }
        orgs, err := recovery.Organizations(shares, ledger, manifest.AuthorityPublicKey, head, item.ObjectID, env.CustodyEpoch)
        if err != nil { return err }
        if len(orgs) < manifest.Threshold { continue }
        plain, err := recovery.Decrypt(vault, env); if err != nil { return err }
        dig := crypto.SHA256(plain)
        sort.Strings(orgs)
        rows = append(rows, map[string]any{
            "active_rewrap_transaction_id": head,
            "custody_epoch": env.CustodyEpoch,
            "data_key_commitment": env.DataKeyCommitment,
            "envelope_version": env.SchemaVersion,
            "logical_path": env.LogicalPath,
            "organizations": orgs,
            "plaintext_sha256": dig,
            "plaintext_size": len(plain),
            "recovery_status": "recovered",
        })
        plaintexts[env.LogicalPath] = plain
        digests = append(digests, dig)
    }
    sort.Slice(rows, func(i,j int) bool { return rows[i]["logical_path"].(string) < rows[j]["logical_path"].(string) })
    var inv []byte
    for _, row := range rows {
        b, err := canon.Marshal(row); if err != nil { return err }
        inv = append(inv, b...); inv = append(inv, '\n')
    }
    root := map[string]any{
        "schema_version": 1, "policy_id": manifest.PolicyID, "evidence_snapshot_sha256": snap,
        "inventory_sha256": crypto.SHA256(inv), "object_digests": digests,
    }
    bind, _ := canon.Marshal(map[string]any{"policy_id": manifest.PolicyID, "snapshot": snap, "inventory": crypto.SHA256(inv), "objects": digests})
    root["recovery_root"] = crypto.SHA256(bind)
    rootBytes, err := canon.Marshal(root); if err != nil { return err }
    staged := map[string][]byte{"inventory.jsonl": inv, "recovery-root.json": append(rootBytes, '\n')}
    for path, data := range plaintexts { staged[filepath.Join("objects", path)] = data }
    statement := map[string]any{"recovery_root": root["recovery_root"], "evidence_snapshot_sha256": snap, "inventory_sha256": crypto.SHA256(inv)}
    auditDoc, err := audit.Sign(vault, statement); if err != nil { return err }
    auditBytes, err := canon.Marshal(auditDoc); if err != nil { return err }
    staged["audit.dsse.json"] = append(auditBytes, '\n')
    if err := publish.Commit(output, staged); err != nil { return err }
    cp.Snapshot = snap; cp.Complete = true
    return checkpoint.Save(output, cp)
}
