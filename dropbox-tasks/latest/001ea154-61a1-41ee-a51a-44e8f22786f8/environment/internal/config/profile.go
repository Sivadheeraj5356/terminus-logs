package config

type RuntimeProfile struct {
	LaneStride         int
	FetchUseByteCredit bool
	MarkScaleByPull    bool
	PlacementHeavyLast bool
}

func RuntimeFromCluster(c ClusterProfile) RuntimeProfile {
	rp := RuntimeProfile{
		LaneStride:         2,
		FetchUseByteCredit: true,
		MarkScaleByPull:    true,
		PlacementHeavyLast: true,
	}
	if c.LaneScan == "full" {
		rp.LaneStride = 2
	}
	if c.FetchCreditMode == "floor" {
		rp.FetchUseByteCredit = true
	}
	if c.MarkStyle == "interval" {
		rp.MarkScaleByPull = true
	}
	if c.GroupProtocol == "cooperative-sticky" {
		rp.PlacementHeavyLast = true
	}
	return rp
}
