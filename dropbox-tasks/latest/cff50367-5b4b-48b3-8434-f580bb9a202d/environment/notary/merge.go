package notary

import "jwksbound.local/mux/model"

// CombineSeal folds incoming seal metadata into a base record.
func CombineSeal(base, incoming model.SealMeta) model.SealMeta {
	out := base
	if incoming.Epoch > out.Epoch {
		out.Epoch = incoming.Epoch
	}
	return out
}
