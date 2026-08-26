// Package sp implements the SPOOLD print/spool supervisor simulator.
//
// The function here is a stub. Implement the commands described in
// /app/docs/spec.md so that `spoold <command> ...` emits the canonical JSON
// the specification defines.
package sp

import "errors"

// Run dispatches a spoold subcommand. args is os.Args[1:].
func Run(args []string) error {
	return errors.New("not implemented")
}
