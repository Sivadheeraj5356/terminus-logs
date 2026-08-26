package main
import ("flag"; "fmt"; "os"; "vaultqualify/internal/inspect")
func main() {
    archive := flag.String("archive", "", "legacy archive")
    flag.Parse()
    if *archive == "" || inspect.CheckLegacy(*archive) != nil { fmt.Fprintln(os.Stderr, "invalid legacy archive"); os.Exit(1) }
}
