package main

import (
	"fmt"
	"os"

	"github.com/spectro/raman-temp/pkg/config"
	"github.com/spectro/raman-temp/pkg/io"
	"github.com/spectro/raman-temp/pkg/results"
	"github.com/spectro/raman-temp/pkg/spectrum"
)

func main() {
	cfg, err := config.Load("/app/config")
	if err != nil {
		fmt.Fprintf(os.Stderr, "config: %v\n", err)
		os.Exit(1)
	}

	spec, err := spectrum.LoadSpectrum(cfg.SpectrumPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "spectrum: %v\n", err)
		os.Exit(2)
	}

	report := results.BuildReport(spec, cfg)

	if err := io.WriteReport(cfg.ReportPath, report); err != nil {
		fmt.Fprintf(os.Stderr, "report: %v\n", err)
		os.Exit(3)
	}
}
