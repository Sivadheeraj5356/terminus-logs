package main

import (
	"fmt"
	"os"

	"baylock/internal/app"
	"baylock/internal/config"
	"baylock/internal/report"
)

func main() {
	if len(os.Args) < 2 {
		fail("usage: bayctl <setup|attempt|enter-ns|unlock|ingest|rebuild|report|audit> ...")
	}
	switch os.Args[1] {
	case "setup":
		runSetup(os.Args[2:])
	case "attempt":
		runAttempt(os.Args[2:])
	case "enter-ns":
		runEnterNS()
	case "unlock":
		runUnlock(os.Args[2:])
	case "ingest":
		runIngest(os.Args[2:])
	case "rebuild":
		runRebuild()
	case "report":
		runReport(os.Args[2:])
	case "audit":
		runAudit(os.Args[2:])
	default:
		fail("unknown command")
	}
}

func runSetup(args []string) {
	path := flagValue(args, "--scenario")
	if path == "" {
		fail("setup requires --scenario")
	}
	sc, err := app.LoadScenario(path)
	if err != nil {
		fail(err.Error())
	}
	if err := app.SetupScenario(sc); err != nil {
		fail(err.Error())
	}
	fmt.Println("setup complete")
}

func runAttempt(args []string) {
	password := flagValue(args, "--password")
	if password == "" {
		fail("attempt requires --password")
	}
	ok, err := app.RecordAttempt(password)
	if err != nil {
		fail(err.Error())
	}
	if ok {
		fmt.Println("attempt accepted")
	} else {
		fmt.Println("attempt rejected")
	}
}

func runEnterNS() {
	if err := app.EnterNamespace(); err != nil {
		fail(err.Error())
	}
	fmt.Println("enter-ns complete")
}

func runUnlock(args []string) {
	principal := flagValue(args, "--principal")
	if principal == "" {
		fail("unlock requires --principal")
	}
	ok, err := app.UnlockPrincipal(principal)
	if err != nil {
		fail(err.Error())
	}
	if ok {
		fmt.Println("unlock complete")
	} else {
		fmt.Println("unlock failed")
	}
}

func runIngest(args []string) {
	batch := flagValue(args, "--batch")
	events := flagValue(args, "--events")
	if batch == "" || events == "" {
		fail("ingest requires --batch and --events")
	}
	ok, err := app.ImportBatch(batch, events)
	if err != nil {
		fail(err.Error())
	}
	if ok {
		fmt.Println("ingest complete")
	} else {
		fmt.Println("ingest skipped")
	}
}

func runRebuild() {
	if _, err := app.RebuildProjection(); err != nil {
		fail(err.Error())
	}
	fmt.Println("rebuild complete")
}

func runReport(args []string) {
	out := flagValue(args, "--out")
	if out == "" {
		out = config.OutputDir + "/lock_ledger.json"
	}
	if err := app.ResetOutput(); err != nil {
		fail(err.Error())
	}
	if err := report.WriteLedger(out); err != nil {
		fail(err.Error())
	}
	fmt.Println("report complete")
}

func runAudit(args []string) {
	out := flagValue(args, "--out")
	if out == "" {
		out = config.OutputDir + "/lock_audit.json"
	}
	if err := app.ResetOutput(); err != nil {
		fail(err.Error())
	}
	if err := app.WriteAuditTrail(out); err != nil {
		fail(err.Error())
	}
	fmt.Println("audit complete")
}

func flagValue(args []string, name string) string {
	for i := 0; i+1 < len(args); i++ {
		if args[i] == name {
			return args[i+1]
		}
	}
	return ""
}

func fail(msg string) {
	fmt.Fprintln(os.Stderr, msg)
	os.Exit(1)
}
