package sidenote

// Annotate prefixes operator note text for ancillary tooling.
func Annotate(msg string) string {
	return "note:" + msg
}
