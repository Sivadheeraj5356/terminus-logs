package p7_pipe

import (
	"balance_lab/p7_chain"
	"balance_lab/p7_emit"
	"balance_lab/p9_types"
)

type Driver struct {
	EnvRoot string
}

func (d *Driver) Run(scen p9_types.Scenario, out string) error {
	arch, err := p7_chain.BuildArchive(d.EnvRoot, scen)
	if err != nil {
		return err
	}
	return p7_emit.Write(out, arch)
}
