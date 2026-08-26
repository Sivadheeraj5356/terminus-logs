package main
import ("flag"; "fmt"; "os"; "strconv"; "vaultqualify/internal/qualify")
func main() {
    vault := flag.String("vault", "/app/vault", "vault path")
    output := flag.String("output", "/output/recovery-set", "output directory")
    epoch := flag.Int("epoch", 0, "qualification epoch")
    flag.Parse()
    if err := qualify.Run(*vault, *output, *epoch); err != nil { fmt.Fprintln(os.Stderr, err); os.Exit(1) }
    _ = strconv.Itoa
}
