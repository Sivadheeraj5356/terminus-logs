package main

import (
	"flag"
	"fmt"
	"os"

	"streamkit/internal/config"
	"streamkit/internal/sim"
)

func main() {
	workloadsPath := flag.String("workloads", "/app/environment/data/workloads.json", "workload profile file")
	clusterPath := flag.String("cluster", "/app/environment/configs/cluster.json", "cluster metadata file")
	reportPath := flag.String("report", "/app/ingest_recovery_report.json", "output report path")
	flag.Parse()

	work, err := config.LoadWorkloads(*workloadsPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "load workloads: %v\n", err)
		os.Exit(1)
	}
	cluster, err := config.LoadCluster(*clusterPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "load cluster: %v\n", err)
		os.Exit(1)
	}
	profile := config.RuntimeFromCluster(cluster)
	report, err := sim.RunAll(work, profile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "run simulation: %v\n", err)
		os.Exit(1)
	}
	if err := sim.WriteReport(*reportPath, report); err != nil {
		fmt.Fprintf(os.Stderr, "write report: %v\n", err)
		os.Exit(1)
	}
}
