package paths

import "os"

func Root() string { return "/app/environment" }
func BuildDir() string { return Root() + "/build" }
func KernelPath() string { return BuildDir() + "/bs7-core" }
func ManifestPath() string {
    if v := os.Getenv("BASINSPAN_MANIFEST"); v != "" { return v }
    return Root() + "/data/manifest.toml"
}
func PairDir() string {
    if v := os.Getenv("BASINSPAN_PAIR_DIR"); v != "" { return v }
    return Root() + "/data/pairs"
}
func OutputDir() string { return "/app/output" }
func VarDir() string { return "/app/var/basinspan" }
