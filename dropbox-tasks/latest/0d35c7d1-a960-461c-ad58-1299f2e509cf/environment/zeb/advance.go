package zeb

// Advance moves the durable counters for one completed arm and reseals the anchor.
func Advance(s *Session, kind, arm string) {
	s.ActiveGen++
	s.Floor = s.ActiveGen
	s.Epoch++
	s.Anchor = SealAnchor(s.ActiveGen, s.Floor, s.Epoch)
	s.LastArm = arm
	_ = kind
}
