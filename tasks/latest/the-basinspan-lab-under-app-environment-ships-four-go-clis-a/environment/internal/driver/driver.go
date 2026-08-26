package driver

import (
    "os"
    "path/filepath"

    "bs7/internal/export"
    "bs7/internal/ingest"
    "bs7/internal/memstore"
    "bs7/internal/persist"
    "bs7/internal/paths"
    "bs7/internal/pipeline"
    "bs7/internal/policy"
)

func Execute(reset bool) error {
    if err := os.MkdirAll(paths.VarDir(), 0o755); err != nil {
        return err
    }
    if err := os.MkdirAll(paths.OutputDir(), 0o755); err != nil {
        return err
    }
    pol, err := policy.Load()
    if err != nil {
        return err
    }
    var gen int
    var led persist.MergeLedger
    var cache memstore.Cache
    if reset {
        _ = os.RemoveAll(paths.VarDir())
        _ = os.MkdirAll(paths.VarDir(), 0o755)
        gen = 1
        led = persist.MergeLedger{Generation: gen, PolicyEpoch: pol.PolicyEpoch, Entries: map[string]persist.LedgerEntry{}}
        cache = memstore.Cache{PolicyEpoch: pol.PolicyEpoch, Entries: map[string]memstore.CacheEntry{}}
    } else {
        led = persist.LoadLedger()
        cache = memstore.Load()
        if led.Generation <= 0 {
            gen = 1
        } else {
            gen = led.Generation + 1
        }
        led.Generation = gen
        led.PolicyEpoch = pol.PolicyEpoch
        if led.Entries == nil {
            led.Entries = map[string]persist.LedgerEntry{}
        }
        if cache.Entries == nil {
            cache.Entries = map[string]memstore.CacheEntry{}
        }
    }

    profiles, err := ingest.LoadManifest(paths.ManifestPath())
    if err != nil {
        return err
    }
    var reportProfiles []export.ProfileResult
    var traces []export.TraceRow
    var journalLines []export.JournalLine
    var acceptedDigests []string
    var lastCert export.Certificate

    for _, prof := range profiles {
        pp := filepath.Join(paths.PairDir(), prof.Pair)
        pair, raw, err := ingest.LoadPair(pp)
        if err != nil {
            return err
        }
        dig := pipeline.PairDigest(raw)
        pr := export.ProfileResult{
            Label: prof.Label, PairID: pair.PairID, PairDigestHex: dig,
        }
        if !ingest.Valid(pair) {
            reportProfiles = append(reportProfiles, pr)
            continue
        }
        key := memstore.CacheKey(dig)
        if ent, ok := cache.Entries[key]; ok && ent.PairDigestHex == dig {
            pr.Accepted = true
            pr.MergeDigestHex = ent.MergeDigestHex
            pr.EvalMSE = ent.EvalMSE
            pr.BarrierValue = ent.BarrierValue
            pr.AlignCost = ent.AlignCost
            pr.NaiveMSE = ent.EvalMSE
            reportProfiles = append(reportProfiles, pr)
            acceptedDigests = append(acceptedDigests, ent.MergeDigestHex)
            continue
        }
        res, err := pipeline.Evaluate(pair, prof.Label, pol)
        if err != nil {
            return err
        }
        pr.Accepted = true
        pr.MergeDigestHex = res.MergeDigestHex
        pr.EvalMSE = res.EvalMSE
        pr.NaiveMSE = res.NaiveMSE
        pr.BarrierValue = res.BarrierValue
        pr.AlignCost = res.AlignCost
        pr.Permutations = res.Permutations
        reportProfiles = append(reportProfiles, pr)
        acceptedDigests = append(acceptedDigests, res.MergeDigestHex)
        cache.Entries[key] = memstore.CacheEntry{
            PairDigestHex: dig, MergeDigestHex: res.MergeDigestHex,
            EvalMSE: res.EvalMSE, BarrierValue: res.BarrierValue, AlignCost: res.AlignCost,
        }
        prev := led.Entries[prof.Label]
        led.Entries[prof.Label] = persist.BumpStable(prev, res.MergeDigestHex, gen)
        traces = append(traces, res.TraceRows...)
        journalLines = append(journalLines, res.Journal)
        lastCert = res.Certificate
        lastCert.Label = prof.Label
    }

    rep := export.Report{
        Generation: gen, PolicyEpoch: pol.PolicyEpoch,
        ReportDigestHex: export.ReportDigest(gen, pol.PolicyEpoch, acceptedDigests),
        Profiles: reportProfiles,
    }
    if err := export.WriteReport(rep); err != nil {
        return err
    }
    if err := export.WriteTrace(traces); err != nil {
        return err
    }
    if err := export.WriteJournal(journalLines); err != nil {
        return err
    }
    if lastCert.Label != "" {
        if err := export.WriteCertificate(lastCert); err != nil {
            return err
        }
    }
    cache.PolicyEpoch = pol.PolicyEpoch
    if err := memstore.Save(cache); err != nil {
        return err
    }
    return persist.SaveLedger(led)
}
