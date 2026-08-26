package boardcmd

import (
	"fmt"
	"os"

	"waxlaneboard/pkg/matchplan"
	"waxlaneboard/pkg/spraydecoy"
	"waxlaneboard/pkg/matchticket"
	"waxlaneboard/pkg/scoreledger"
	"waxlaneboard/pkg/rinklayout"
	"waxlaneboard/pkg/diskset"
)

func Run(args []string) error {
	if len(args) < 1 {
		return fmt.Errorf("usage: waxlane-allot <chalk|allot|claim|buff-catalog> ...")
	}
	switch args[0] {
	case "chalk":
		return runChalk(args[1:])
	case "allot":
		return runAllot(args[1:])
	case "claim":
		return runClaim(args[1:])
	case "buff-catalog":
		return runBuff(args[1:])
	default:
		return fmt.Errorf("unknown command %s", args[0])
	}
}

func flagMap(args []string) map[string]string {
	m := map[string]string{}
	for i := 0; i+1 < len(args); i += 2 {
		if len(args[i]) > 2 && args[i][:2] == "--" {
			m[args[i][2:]] = args[i+1]
		}
	}
	return m
}

func runChalk(args []string) error {
	f := flagMap(args)
	courtPath := f["court"]
	lotsPath := f["lots"]
	slatePath := f["slate"]
	epochPath := f["epoch"]
	if courtPath == "" || lotsPath == "" || slatePath == "" || epochPath == "" {
		return fmt.Errorf("chalk requires --court --lots --slate --epoch")
	}
	court, err := rinklayout.Load(courtPath)
	if err != nil {
		return err
	}
	man, err := diskset.Load(lotsPath)
	if err != nil {
		return err
	}
	if err := diskset.ValidateIDs(man.Lots); err != nil {
		return err
	}
	epoch, err := matchticket.ReadEpoch(epochPath)
	if err != nil {
		return err
	}
	slate, err := matchticket.Build(court, man.Lots, epoch)
	if err != nil {
		return err
	}
	if err := matchticket.Write(slatePath, slate); err != nil {
		return err
	}
	return matchticket.WriteEpoch(epochPath, epoch+1)
}

func runAllot(args []string) error {
	f := flagMap(args)
	courtPath := f["court"]
	slatePath := f["slate"]
	ledgerPath := f["ledger"]
	if courtPath == "" || slatePath == "" || ledgerPath == "" {
		return fmt.Errorf("allot requires --court --slate --ledger")
	}
	court, err := rinklayout.Load(courtPath)
	if err != nil {
		return err
	}
	slate, err := matchticket.Load(slatePath)
	if err != nil {
		return err
	}
	man, err := diskset.Load("/app/data/disk-packages.json")
	if err != nil {
		return err
	}
	dec := matchplan.Solve(court, man.Lots)
	_ = slate
	led := scoreledger.Build(court, slate, dec)
	return scoreledger.Write(ledgerPath, led)
}

func runClaim(args []string) error {
	f := flagMap(args)
	if err := runChalk([]string{
		"--court", f["court"],
		"--lots", f["lots"],
		"--slate", f["slate"],
		"--epoch", f["epoch"],
	}); err != nil {
		return err
	}
	return runAllot([]string{
		"--court", f["court"],
		"--slate", f["slate"],
		"--ledger", f["ledger"],
	})
}

func runBuff(args []string) error {
	f := flagMap(args)
	path := f["catalog"]
	if path == "" {
		return fmt.Errorf("buff-catalog requires --catalog")
	}
	return spraydecoy.Print(path)
}

func MustMain() {
	if err := Run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
