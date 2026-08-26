package export

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"

	"rutile/basalt"
	"rutile/flint"
	"rutile/gneiss"
	"rutile/internal/types"
	"rutile/mica"
	"rutile/slate"
	"rutile/vein"
)

func loadJSON[T any](path string, out *T) error {
	raw, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(raw, out)
}

func levelOf(levels map[string]int, principal string) int {
	if v, ok := levels[principal]; ok {
		return v
	}
	return 0
}

func appendGated(edges *[]types.EdgeRow, pairs [][2]string, channel string, levels map[string]int, constraints []types.ConstraintRow, usage []types.UsageRow) {
	for _, pair := range pairs {
		srcLevel := levelOf(levels, pair[0])
		dstLevel := levelOf(levels, pair[1])
		if !flint.Allows(constraints, srcLevel, dstLevel) {
			continue
		}
		*edges = append(*edges, types.EdgeRow{
			From: pair[0], To: pair[1], Channel: channel,
			Weight: basalt.UsageWeight(usage, pair[0], pair[1]),
		})
	}
}

func appendK8s(edges *[]types.EdgeRow, pairs [][2]string, usage []types.UsageRow) {
	for _, pair := range pairs {
		*edges = append(*edges, types.EdgeRow{
			From: pair[0], To: pair[1], Channel: "k8s",
			Weight: basalt.UsageWeight(usage, pair[0], pair[1]),
		})
	}
}

func RunAnalyze(profile, root, outPath string) error {
	base := filepath.Join(root, "profiles", profile)
	var users []types.UserRow
	var memberships []types.MembershipRow
	var assume []types.AssumeRow
	var constraints []types.ConstraintRow
	var usage []types.UsageRow
	var identities []types.IdentityRow
	var bindings []types.BindingRow
	var aggregate []types.AggregateRow
	var federation []types.FederationRow
	levels := map[string]int{}
	if err := loadJSON(filepath.Join(base, "iam", "users.json"), &users); err != nil {
		return err
	}
	if err := loadJSON(filepath.Join(base, "groups", "memberships.json"), &memberships); err != nil {
		return err
	}
	if err := loadJSON(filepath.Join(base, "roles", "assume.json"), &assume); err != nil {
		return err
	}
	if err := loadJSON(filepath.Join(base, "permissions", "constraints.json"), &constraints); err != nil {
		return err
	}
	if err := loadJSON(filepath.Join(base, "permissions", "usage.json"), &usage); err != nil {
		return err
	}
	if err := loadJSON(filepath.Join(base, "cloud", "identities.json"), &identities); err != nil {
		return err
	}
	if err := loadJSON(filepath.Join(base, "rbac", "bindings.json"), &bindings); err != nil {
		return err
	}
	if err := loadJSON(filepath.Join(base, "rbac", "aggregate.json"), &aggregate); err != nil {
		return err
	}
	if err := loadJSON(filepath.Join(base, "cloud", "federation.json"), &federation); err != nil {
		return err
	}
	if err := loadJSON(filepath.Join(base, "catalog", "levels.json"), &levels); err != nil {
		return err
	}

	var edges []types.EdgeRow
	appendGated(&edges, vein.GroupPairs(memberships), "group", levels, constraints, usage)
	appendGated(&edges, slate.RolePairs(assume), "role", levels, constraints, usage)
	appendK8s(&edges, vein.K8sPairs(bindings, aggregate), usage)
	for _, row := range federation {
		edges = append(edges, types.EdgeRow{
			From: row.From, To: row.To, Channel: "cloud",
			Weight: basalt.UsageWeight(usage, row.From, row.To),
		})
	}
	sort.Slice(edges, func(i, j int) bool {
		if edges[i].Channel != edges[j].Channel {
			return edges[i].Channel < edges[j].Channel
		}
		if edges[i].From != edges[j].From {
			return edges[i].From < edges[j].From
		}
		if edges[i].To != edges[j].To {
			return edges[i].To < edges[j].To
		}
		return edges[i].Weight < edges[j].Weight
	})

	entries := mica.EntryNodes(identities)
	crowns := map[string]struct{}{}
	for _, row := range identities {
		if row.Crown {
			crowns[row.ID] = struct{}{}
		}
	}
	adj := map[string][]string{}
	for _, row := range edges {
		adj[row.From] = append(adj[row.From], row.To)
	}
	chains := mica.PathRows(entries, crowns, adj)

	report := types.EscalationReport{
		Profile: profile, IdentityCount: len(users), Edges: edges,
		Chains: chains, ReportDigestHex: gneiss.Witness(edges),
	}
	raw, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(outPath, append(raw, byte('\n')), 0o644)
}
