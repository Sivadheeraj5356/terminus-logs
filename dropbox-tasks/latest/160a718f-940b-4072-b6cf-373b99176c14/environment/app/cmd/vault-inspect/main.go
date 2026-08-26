package main
import ("flag"; "fmt"; "os"; "vaultqualify/internal/inspect")
func main() {
    vault := flag.String("vault", "/app/vault", "vault path")
    flag.Parse()
    if err := inspect.Print(*vault); err != nil { fmt.Fprintln(os.Stderr, err); os.Exit(1) }
}
