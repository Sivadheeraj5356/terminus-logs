package main

import (
    "flag"
    "fmt"
    "os"

    "rutile/internal/export"
)

func main() {
    if len(os.Args) < 2 {
        fmt.Fprintln(os.Stderr, "usage: escalctl analyze")
        os.Exit(2)
    }
    if os.Args[1] != "analyze" {
        fmt.Fprintln(os.Stderr, "unknown subcommand")
        os.Exit(2)
    }
    fs := flag.NewFlagSet("analyze", flag.ExitOnError)
    profile := fs.String("profile", "", "holdout profile")
    root := fs.String("root", "", "data root")
    out := fs.String("out", "", "output path")
    _ = fs.Parse(os.Args[2:])
    if *profile == "" || *root == "" || *out == "" {
        fmt.Fprintln(os.Stderr, "missing required flags")
        os.Exit(2)
    }
    if err := export.RunAnalyze(*profile, *root, *out); err != nil {
        fmt.Fprintln(os.Stderr, err)
        os.Exit(1)
    }
}
