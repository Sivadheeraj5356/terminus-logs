package main

import (
    "encoding/json"
    "flag"
    "fmt"
    "os"

    "example.com/coastal/beacon-drift/internal/packets"
)

func main() {
    input := flag.String("input", "", "packet JSON to validate")
    output := flag.String("output", "", "where to write validation result")
    profileID := flag.String("profile", "", "beacon profile identifier")
    flag.Parse()

    if *input == "" || *output == "" || *profileID == "" {
        fmt.Fprintln(os.Stderr, "usage: beacon-drift --profile PROFILE --input packet.json --output result.json")
        os.Exit(2)
    }

    result, err := packets.ValidatePacket(*profileID, *input)
    if err != nil {
        fmt.Fprintln(os.Stderr, err.Error())
        os.Exit(1)
    }

    f, err := os.Create(*output)
    if err != nil {
        fmt.Fprintf(os.Stderr, "cannot create output: %v\n", err)
        os.Exit(1)
    }
    defer f.Close()

    enc := json.NewEncoder(f)
    enc.SetIndent("", "  ")
    if err := enc.Encode(result); err != nil {
        fmt.Fprintf(os.Stderr, "cannot encode output: %v\n", err)
        os.Exit(1)
    }
}
