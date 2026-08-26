package replay

import "mdllab/internal/settle"

func closeLethal(state settle.OutcomeState, actors settle.ActorPair, stepID int) settle.SettleVerdict {
	return settle.ApplySettle(state, actors, stepID)
}
