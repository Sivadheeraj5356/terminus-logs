// Package chandeck replays one recorded Chan (bi tu, 100-card) winning
// declaration and writes the byte-exact referee account.
package chandeck

// Trace returns the placeholder referee account for one recorded Chan
// declaration. The real replay — confirming the declaration, naming the
// honours, totalling the diem, charging fines and settling the four seats —
// is left for the candidate to implement so that the command reproduces the
// byte-stable account described in docs/rules.md.
func Trace(_ []byte) string {
	return "Chan = bi-tu 100-card\nResult = incomplete\n"
}
