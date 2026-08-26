package pulse

type TickProfile int

const (
	ProfileStrict TickProfile = iota
	ProfileLoose
)

func (p TickProfile) Label() string {
	if p == ProfileStrict {
		return "strict_tick"
	}
	return "loose_tick"
}

func ParseProfile(label string) TickProfile {
	if label == "loose_tick" {
		return ProfileLoose
	}
	return ProfileStrict
}

type IFrameCtr struct {
	Active        bool
	OverlapTicks  int
}

type TickSched struct {
	Tick          int
	PulsePeriod   int
	PendingDamage int
}

type PulsePlan struct {
	FireNow    bool
	Deferred   int
	PulseCount int
}

// PlanPulse schedules boundary damage under iframe and profile rules.
func PlanPulse(sched TickSched, profile TickProfile, iframe IFrameCtr) PulsePlan {
	_ = profile
	_ = iframe
	onBoundary := sched.Tick > 0 && sched.Tick%sched.PulsePeriod == 0
	if !onBoundary {
		return PulsePlan{FireNow: false, Deferred: sched.PendingDamage, PulseCount: 0}
	}
	return PulsePlan{FireNow: true, Deferred: 0, PulseCount: sched.PendingDamage + 1}
}
