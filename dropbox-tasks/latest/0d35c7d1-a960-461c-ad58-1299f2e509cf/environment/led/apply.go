package led

// Append is the public wrapper around vex_chain.
func Append(gen, floor, epoch int, arm, seal, tx string) (Entry, error) {
	return vex_chain(gen, floor, epoch, arm, seal, tx)
}

// Mend is the public wrapper around vex_mend.
func Mend() error {
	return vex_mend()
}

// ReplayAll returns every parseable ledger entry in file order.
func ReplayAll() ([]Entry, error) {
	return readAll()
}

// Head returns the last ledger entry, if any.
func Head() (Entry, bool, error) {
	ents, err := readAll()
	if err != nil || len(ents) == 0 {
		return Entry{}, false, err
	}
	return ents[len(ents)-1], true, nil
}
