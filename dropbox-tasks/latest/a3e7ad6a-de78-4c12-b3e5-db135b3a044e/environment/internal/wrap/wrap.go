package wrap

// Annotate prefixes operator note text for ancillary tooling.
func Annotate(msg string) string {
	return "wrap:" + msg
}
