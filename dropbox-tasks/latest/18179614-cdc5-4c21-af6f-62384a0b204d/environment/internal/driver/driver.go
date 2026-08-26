package driver

import (
	"fmt"
	"os"
	"path/filepath"

	"ot7/internal/bridge"
	"ot7/internal/export"
	"ot7/internal/ingest"
	"ot7/internal/memstore"
	"ot7/internal/paths"
	"ot7/internal/policy"
	"ot7/internal/runbook"
)

type Runner struct {
	InstanceDir string
	Reset       bool
}

func (r Runner) Execute(manifestPath string) (export.Report, error) {
	if r.Reset {
		_ = os.RemoveAll(paths.Var)
		_ = os.MkdirAll(paths.Var, 0o777)
	}
	_ = os.MkdirAll(paths.Output, 0o777)
	pol := policy.Load(filepath.Join(paths.Data, "policy.toml"))
	ld := runbook.Load()
	if r.Reset || ld.Generation == 0 {
		ld.Generation = 1
	} else {
		ld.Generation++
	}
	ld.PolicyEpoch = pol.Epoch
	cstore := memstore.Load()
	profiles, err := ingest.ParseManifest(manifestPath)
	if err != nil {
		return export.Report{}, err
	}
	var results []export.ProfileResult
	var traceRows [][]string
	var acceptedDigests []string
	for _, prof := range profiles {
		inst, err := ingest.LoadInstance(r.InstanceDir, prof.File)
		if err != nil {
			results = append(results, export.ProfileResult{Label: prof.Label, Accepted: false})
			continue
		}
		instDigest := export.InstanceDigest(inst.Raw)
		resp, err := bridge.Compute(inst, pol.MaxIters, pol.Tol, nil, nil)
		if err != nil || !resp.Ok {
			results = append(results, export.ProfileResult{
				Label: prof.Label, InstanceID: inst.InstanceID, Accepted: false,
				Rows: len(inst.Supply), Cols: len(inst.Demand),
			})
			continue
		}
		pr := export.ProfileResult{
			Label:       prof.Label,
			InstanceID:  inst.InstanceID,
			Accepted:    resp.Accepted,
			Rows:        len(inst.Supply),
			Cols:        len(inst.Demand),
			Wasserstein: resp.Wasserstein,
		}
		if resp.Accepted {
			pr.PlanDigestHex = export.PlanDigest(resp.Plan)
			acceptedDigests = append(acceptedDigests, pr.PlanDigestHex)
			key := memstore.Key(instDigest, pol.Epoch)
			cstore.Put(key, memstore.Entry{
				InstanceDigestHex: instDigest,
				PlanDigestHex:     pr.PlanDigestHex,
				Wasserstein:       pr.Wasserstein,
				Rows:              pr.Rows,
				Cols:              pr.Cols,
				F:                 resp.F,
				G:                 resp.G,
			})
			runbook.BumpStable(&ld, prof.Label, pr.PlanDigestHex, ld.Generation)
			for i := range resp.Plan {
				for j := range resp.Plan[i] {
					traceRows = append(traceRows, []string{
						prof.Label,
						fmt.Sprintf("%d", i),
						fmt.Sprintf("%d", j),
						fmt.Sprintf("%.17g", resp.Plan[i][j]),
						fmt.Sprintf("%.17g", inst.Cost[i][j]),
					})
				}
			}
		} else {
			pr.PlanDigestHex = ""
			pr.Wasserstein = 0
		}
		results = append(results, pr)
	}
	rep := export.Report{
		Generation:      ld.Generation,
		PolicyEpoch:     pol.Epoch,
		ReportDigestHex: export.ReportDigest(ld.Generation, pol.Epoch, acceptedDigests),
		Profiles:        results,
	}
	if err := export.WriteReport(rep); err != nil {
		return rep, err
	}
	if err := export.WriteTrace(traceRows); err != nil {
		return rep, err
	}
	if err := cstore.Save(); err != nil {
		return rep, err
	}
	if err := ld.Save(); err != nil {
		return rep, err
	}
	return rep, nil
}
