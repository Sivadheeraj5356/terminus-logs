package main

import (
	"fmt"
	"os"
	"strconv"
)

func usage() {
	fmt.Fprintf(os.Stderr, `crosspay - a cross-border payroll CLI backed by SQLite

Usage:
  crosspay init
  crosspay add-employee <name> --rate <micros_per_hour>
  crosspay employees
  crosspay log-hours <employee> <hours> --now <epoch>
  crosspay gross <employee>
  crosspay schedules
  crosspay brackets --region <REGION>
  crosspay withhold --region <REGION> --gross <micros>
  crosspay net <employee> --region <REGION>
  crosspay country-info --country <cca2>
  crosspay country-pay <employee> --country <cca2> --now <epoch>
  crosspay assign <employee> --country <cca2>
  crosspay social <employee> --country <cca2>
  crosspay convert --amount <micros> --from <CUR>
  crosspay report

Options:
  --rate <m>        pay rate in micro-units of major currency per hour
  --region <R>      statutory schedule region key (see docs/spec.md)
  --gross <m>       gross pay in micro-units (withhold)
  --country <cc>    ISO 3166-1 alpha-2 country code (country-info, country-pay)
  --amount <m>      amount in micro-units to convert (convert)
  --from <CUR>      ISO 4217 source currency code (convert)
  --now <epoch>     override current Unix time for deterministic runs

Environment:
  CROSSPAY_NOW      override current Unix time (epoch seconds)

All amounts are integer micro-units (1000000 micro-units = one major currency
unit). Country metadata is read from the bundled reference dataset at
/app/reference/countries.json. See /app/docs/spec.md for the authoritative
contract.
`)
}

// nowFlag holds the value of a --now flag, or -1 when absent.
var nowFlag int64 = -1

// NowUnix returns the current time, honoring --now and CROSSPAY_NOW overrides.
// The --now flag (parsed out of os.Args by stripNow) takes precedence over the
// CROSSPAY_NOW environment variable.
func NowUnix() int64 {
	if nowFlag >= 0 {
		return nowFlag
	}
	if s := os.Getenv("CROSSPAY_NOW"); s != "" {
		if n, err := strconv.ParseInt(s, 10, 64); err == nil {
			return n
		}
	}
	return 0
}

// stripNow removes a "--now <epoch>" pair from args wherever it appears and
// records the value in nowFlag. Returns the filtered args.
func stripNow(args []string) []string {
	out := []string{}
	for i := 0; i < len(args); i++ {
		if args[i] == "--now" && i+1 < len(args) {
			if n, err := strconv.ParseInt(args[i+1], 10, 64); err == nil {
				nowFlag = n
			}
			i++
			continue
		}
		out = append(out, args[i])
	}
	return out
}

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(1)
	}

	cmd := os.Args[1]
	rest := stripNow(os.Args[2:])

	switch cmd {
	case "init":
		CmdInit()
	case "add-employee":
		CmdAddEmployee(rest)
	case "employees":
		CmdEmployees(rest)
	case "log-hours":
		CmdLogHours(rest)
	case "gross":
		CmdGross(rest)
	case "schedules":
		CmdSchedules(rest)
	case "brackets":
		CmdBrackets(rest)
	case "withhold":
		CmdWithhold(rest)
	case "net":
		CmdNet(rest)
	case "country-info":
		CmdCountryInfo(rest)
	case "country-pay":
		CmdCountryPay(rest)
	case "assign":
		CmdAssign(rest)
	case "social":
		CmdSocial(rest)
	case "convert":
		CmdConvert(rest)
	case "report":
		CmdReport(rest)
	default:
		fmt.Fprintf(os.Stderr, "unknown command: %s\n", cmd)
		usage()
		os.Exit(1)
	}
}
