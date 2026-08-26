#!/bin/bash
set -euo pipefail

cd /app

python3 <<'PY'
from pathlib import Path

profilefilter = Path("/app/cargograph/profilefilter.go")
text = profilefilter.read_text()
old = """func FilterRuntimeFeatures(features []string, profile string, tags FeatureTags) []string {
\t_, _ = profile, tags
\treturn SortFeatures(features)
}"""
new = """func FilterRuntimeFeatures(features []string, profile string, tags FeatureTags) []string {
\tif profile != "release" {
\t\treturn SortFeatures(features)
\t}
\tdev := make(map[string]struct{}, len(tags.DevOnlyFeatures))
\tfor _, f := range tags.DevOnlyFeatures {
\t\tdev[f] = struct{}{}
\t}
\tout := make([]string, 0, len(features))
\tfor _, f := range features {
\t\tif _, skip := dev[f]; skip {
\t\t\tcontinue
\t\t}
\t\tout = append(out, f)
\t}
\treturn SortFeatures(out)
}"""
if old not in text:
    raise SystemExit("profilefilter.go unexpected content")
profilefilter.write_text(text.replace(old, new))

workspace = Path("/app/cargograph/workspace.go")
text = workspace.read_text()
old = """func SourceLabel(crate string, declared map[string]DeclaredDep, workspaceMembers map[string]struct{}, fromWorkspacePin bool) string {
\t_, _, _, _ = crate, declared, workspaceMembers, fromWorkspacePin
\treturn "transitive"
}"""
new = """func SourceLabel(crate string, declared map[string]DeclaredDep, workspaceMembers map[string]struct{}, fromWorkspacePin bool) string {
\tif _, ok := declared[crate]; ok {
\t\tif _, member := workspaceMembers[crate]; member {
\t\t\treturn "workspace_declared"
\t\t}
\t\treturn "declared"
\t}
\tif fromWorkspacePin {
\t\treturn "workspace"
\t}
\treturn "transitive"
}"""
if old not in text:
    raise SystemExit("workspace.go unexpected content")
workspace.write_text(text.replace(old, new))

Path("/app/cargograph/expand.go").write_text(
    """package cargograph

func ExpandFeatureAliases(features []string, aliases map[string][]string) []string {
\tif len(aliases) == 0 {
\t\treturn SortFeatures(features)
\t}
\tout := make([]string, 0, len(features))
\tfor _, feat := range features {
\t\tif expanded, ok := aliases[feat]; ok {
\t\t\tout = UnionFeatures(out, expanded)
\t\t} else {
\t\t\tout = append(out, feat)
\t\t}
\t}
\treturn SortFeatures(out)
}
"""
)

conflicts = Path("/app/cargograph/conflicts.go")
text = conflicts.read_text()
old = """\t\t} else {
\t\t\tc.ResolutionReason = "nearest"
\t\t}"""
new = """\t\t} else if c.ResolutionReason != "unified" {
\t\t\tc.ResolutionReason = "nearest"
\t\t}"""
if old not in text:
    raise SystemExit("conflicts.go unexpected content")
conflicts.write_text(text.replace(old, new))

walk = Path("/app/cargograph/walk.go")
text = walk.read_text()

if "func declaredProcessingOrder" in text:
    text = text.replace(
        "func declaredProcessingOrder(sc Scenario) []DeclaredDep {\n"
        "\tout := append([]DeclaredDep(nil), sc.Declared...)\n"
        "\tsort.Slice(out, func(i, j int) bool {\n"
        "\t\treturn out[i].Crate < out[j].Crate\n"
        "\t})\n"
        "\treturn out\n"
        "}\n\n",
        "",
    )
    text = text.replace("for _, d := range declaredProcessingOrder(sc) {", "for _, d := range sc.Declared {")

text = text.replace(
    "\t\tif out[i].EdgeID != out[j].EdgeID {\n"
    "\t\t\treturn out[i].EdgeID < out[j].EdgeID\n"
    "\t\t}\n"
    "\t\treturn out[i].Child < out[j].Child",
    "\t\tif out[i].Child != out[j].Child {\n"
    "\t\t\treturn out[i].Child < out[j].Child\n"
    "\t\t}\n"
    "\t\treturn out[i].EdgeID < out[j].EdgeID",
)

text = text.replace(
    "\taddRejected := func(crate, selected, rejected string) {",
    "\taddRejected := func(crate, selected, rejected, reason string) {",
)
text = text.replace(
    "\t\t\t\tResolutionReason: \"nearest\",",
    "\t\t\t\tResolutionReason: reason,",
)
text = text.replace(
    "\t\tc.RejectedVersions = SortVersions(c.RejectedVersions)\n"
    "\t\t\tc.Severity = ConflictSeverity(selected, c.RejectedVersions)\n"
    "\t\t}\n"
    "\t\tres.conflicts[key] = c",
    "\t\tc.RejectedVersions = SortVersions(c.RejectedVersions)\n"
    "\t\t\tc.Severity = ConflictSeverity(selected, c.RejectedVersions)\n"
    "\t\t}\n"
    "\t\tif reason == \"unified\" {\n"
    "\t\t\tc.ResolutionReason = \"unified\"\n"
    "\t\t}\n"
    "\t\tres.conflicts[key] = c",
)

text = text.replace(
    "\t\tif depth > prev.depth {\n"
    "\t\t\tkeep = contender\n"
    "\t\t\taddRejected(crate, version, prev.version)\n"
    "\t\t} else if depth < prev.depth {\n"
    "\t\t\taddRejected(crate, prev.version, version)\n"
    "\t\t\treturn prev.crateKey\n"
    "\t\t} else if parentKey > prev.parentKey {\n"
    "\t\t\tkeep = contender\n"
    "\t\t\taddRejected(crate, version, prev.version)\n"
    "\t\t} else {\n"
    "\t\t\taddRejected(crate, prev.version, version)\n"
    "\t\t\treturn prev.crateKey\n"
    "\t\t}",
    "\t\tif depth < prev.depth {\n"
    "\t\t\tkeep = contender\n"
    "\t\t\taddRejected(crate, version, prev.version, \"nearest\")\n"
    "\t\t} else if depth > prev.depth {\n"
    "\t\t\taddRejected(crate, prev.version, version, \"nearest\")\n"
    "\t\t\treturn prev.crateKey\n"
    "\t\t} else if parentKey < prev.parentKey {\n"
    "\t\t\tkeep = contender\n"
    "\t\t\taddRejected(crate, version, prev.version, \"nearest\")\n"
    "\t\t} else {\n"
    "\t\t\taddRejected(crate, prev.version, version, \"unified\")\n"
    "\t\t\treturn prev.crateKey\n"
    "\t\t}",
)

purge = """\t\tif keep.crateKey != prev.crateKey {
\t\t\tstale := make([]string, 0)
\t\t\tfor key, c := range res.conflicts {
\t\t\t\tif c.Crate == crate && c.SelectedVersion != keep.version {
\t\t\t\t\tstale = append(stale, key)
\t\t\t\t}
\t\t\t}
\t\t\tfor _, key := range stale {
\t\t\t\tdelete(res.conflicts, key)
\t\t\t}
\t\t\tres.conflictRowsPurged += len(stale)
\t\t\tdelete(res.crates, prev.crateKey)"""
if purge not in text:
    text = text.replace(
        "\t\tif keep.crateKey != prev.crateKey {\n\t\t\tdelete(res.crates, prev.crateKey)",
        purge,
    )

walk.write_text(text)
PY

make clean || true
make build
make run

test -s /app/build/feature_resolution_report.json
