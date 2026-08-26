package replay

import "mdllab/internal/pulse"

func planForRow(sched pulse.TickSched, profile pulse.TickProfile, iframe pulse.IFrameCtr) pulse.PulsePlan {
	return pulse.PlanPulse(sched, profile, iframe)
}
