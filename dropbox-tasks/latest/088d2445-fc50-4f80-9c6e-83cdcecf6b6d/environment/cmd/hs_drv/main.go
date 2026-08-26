package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"hsdrive/internal/arms"
	"hsdrive/internal/decoy"
	"hsdrive/internal/digest"
	"hsdrive/internal/emit"
	"hsdrive/internal/fold"
	"hsdrive/internal/journal"
	"hsdrive/internal/nest"
	"hsdrive/internal/store"
	"hsdrive/internal/warm"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func envOr(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func readLines(path string) ([]string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var out []string
	for _, ln := range strings.Split(string(raw), "\n") {
		ln = strings.TrimSpace(ln)
		if ln != "" {
			out = append(out, ln)
		}
	}
	return out, nil
}

func main() {
	all := flag.Bool("all-lanes", false, "score every lane")
	warmFlag := flag.Bool("warm", false, "warm restart path")
	rots := flag.String("rotations", "", "path to rot_d.toml")
	flag.Parse()
	if !*all {
		fmt.Fprintln(os.Stderr, "require --all-lanes")
		os.Exit(2)
	}
	if err := run(*rots, *warmFlag); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(rotPath string, warmFlag bool) error {
	root := envOr("DRV_ROOT", "/app/environment")
	outRoot := envOr("DRV_OUT", "/app/output")
	if rotPath == "" {
		rotPath = filepath.Join(root, "docs", "rot_d.toml")
	}
	stage := filepath.Join(outRoot, "stage")
	if err := os.MkdirAll(stage, 0o755); err != nil {
		return err
	}

	ids, err := readLines(filepath.Join(root, "data", "id_list.txt"))
	if err != nil {
		return err
	}
	keys, err := store.Keys(filepath.Join(root, "data", "store_q.sqlite"))
	if err != nil {
		return err
	}
	binds, err := store.Binds(filepath.Join(root, "data", "store_q.sqlite"))
	if err != nil {
		return err
	}
	rotRows, armIDs, err := arms.Parse(rotPath)
	if err != nil {
		return err
	}

	base := []string{"orb-a", "orb-b", "orb-c", "orb-d"}
	alg := arms.Remap(base, rotRows)
	sort.Strings(alg)
	fp := strings.Join(alg, ",")

	jHold, err := journal.Materialize(
		filepath.Join(root, "data", "annex44"),
		filepath.Join(root, "data", "wal44", "events.jl"),
		filepath.Join(root, "data", "wal44", "ckpt_idx.toml"),
	)
	if err != nil {
		return err
	}
	_ = os.WriteFile(filepath.Join(stage, "gen_stamp.txt"), []byte(fmt.Sprintf("%d\n", len(jHold.Seal))), 0o644)

	cachePath := filepath.Join(stage, "digest_cache.json")
	stagePath := filepath.Join(stage, "summary.json")
	var dig string
	if warmFlag && warm.StageLooksGreen(stagePath) {
		if cached, ok := warm.ReadCachedDigest(cachePath, fp, jHold.Seal); ok {
			dig = cached
		}
	}
	if dig == "" {
		dig, err = fold.Digest(jHold.Segs, keys, fp, jHold.Seal, stage)
		if err != nil {
			return err
		}
	}

	gens := [][]float64{
		{1.0, 0.0, 0.0, 0.0},
		{0.0, 1.0, 0.5, 0.0},
		{0.0, 0.0, 1.0, 0.25},
	}
	ord := []int{0, 2, 1}
	span, err := nest.Reduce(gens, 3, ord, len(alg), len(fp))
	if err != nil {
		return err
	}

	var script []emit.Row
	var cites [][]any
	for _, rid := range []uint64{1001, 1002, 1003, 1004} {
		rec, err := emit.Script(rid, binds)
		if err != nil {
			return err
		}
		script = append(script, rec)
		cites = append(cites, []any{rec.RowID, rec.BindRef})
	}

	type lane struct {
		AlgKeys   []string  `json:"alg_keys"`
		CitePairs [][]any   `json:"cite_pairs"`
		DigestHex string    `json:"digest_hex"`
		LaneID    string    `json:"lane_id"`
		NestDepth int       `json:"nest_depth"`
		NestSpan  []float64 `json:"nest_span"`
		ScriptRows []emit.Row `json:"script_rows"`
		SegOrder  []int     `json:"seg_order"`
	}
	lanes := make([]lane, 0, len(ids))
	for _, id := range ids {
		lanes = append(lanes, lane{
			AlgKeys:    append([]string{}, alg...),
			CitePairs:  cites,
			DigestHex:  dig,
			LaneID:     id,
			NestDepth:  3,
			NestSpan:   append([]float64{}, span...),
			ScriptRows: script,
			SegOrder:   []int{0, 1, 2},
		})
	}

	lanesJSON, err := json.Marshal(lanes)
	if err != nil {
		return err
	}
	runDig := digest.Hex(lanesJSON)

	rep := map[string]any{
		"lane_ids":   ids,
		"lanes":      lanes,
		"rot_arms":   armIDs,
		"run_digest": runDig,
	}
	blob, err := json.Marshal(rep)
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(outRoot, "audit_report.json"), blob, 0o644); err != nil {
		return err
	}
	summary := fmt.Sprintf(`{"status":"%s","lane_count":%d,"digest_echo":"%s"}`,
		decoy.EchoStatus(true), len(ids), dig)
	return os.WriteFile(stagePath, []byte(summary+"\n"), 0o644)
}
