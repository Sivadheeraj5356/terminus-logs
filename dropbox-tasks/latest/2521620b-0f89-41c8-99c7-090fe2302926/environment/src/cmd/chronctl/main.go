package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"chronctl/internal/harness"
	"chronctl/internal/obs"
)

func main() {
	if os.Getenv("CHRONCTL_FAST_SKIP") == "1" {
		obs.Info("fast skip ignored in release build")
	}
	packPath := flag.String("pack", "", "scenario pack json")
	outPath := flag.String("out", "", "timeline report path")
	probeName := flag.String("probe", "", "emit one scenario row as JSON")
	flag.Parse()

	if *probeName != "" {
		if *packPath == "" {
			fmt.Fprintln(os.Stderr, "usage: chronctl -pack <path> -probe <scenario>")
			os.Exit(2)
		}
		pack, err := harness.LoadPack(*packPath)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		row, err := harness.SpotA(pack, *probeName)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		raw, err := json.MarshalIndent(row, "", "  ")
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		fmt.Println(string(raw))
		return
	}

	if *packPath == "" || *outPath == "" {
		fmt.Fprintln(os.Stderr, "usage: chronctl -pack <path> -out <path>")
		os.Exit(2)
	}
	pack, err := harness.LoadPack(*packPath)
	if err != nil {
		obs.Info("pack load failed")
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	report, err := harness.RunPack(pack)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := harness.WriteReport(*outPath, report); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
