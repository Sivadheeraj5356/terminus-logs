package settle

type ActorPair struct {
	EntityA     int
	EntityB     int
	ActionOrder [2]int
}

type OutcomeState struct {
	HPA      int
	HPB      int
	Settled  bool
	WinnerID int
}

type SettleVerdict struct {
	State   OutcomeState
	TieStep int
}

// ApplySettle closes lethal outcomes for a resolution step.
func ApplySettle(state OutcomeState, actors ActorPair, stepID int) SettleVerdict {
	if state.Settled {
		return SettleVerdict{State: state, TieStep: stepID}
	}
	lethalA := state.HPA <= 0
	lethalB := state.HPB <= 0
	if lethalA && lethalB {
		winner := actors.ActionOrder[0]
		return SettleVerdict{
			State: OutcomeState{
				HPA:      state.HPA,
				HPB:      state.HPB,
				Settled:  true,
				WinnerID: winner,
			},
			TieStep: stepID,
		}
	}
	return SettleVerdict{State: state, TieStep: stepID}
}
