package cli

import "fmt"

type ExitError struct {
	Code    int
	Message string
}

func (e *ExitError) Error() string { return e.Message }

func fail(reason string) error {
	return &ExitError{Code: 2, Message: "error: " + reason + "\n"}
}

// Stub CLI: always admit. Rebuild from /app/docs/.
func Run(args []string) error {
	if len(args) == 0 || args[0] != "verify" {
		return fail("usage")
	}
	fmt.Print("ok kid=stub digest=stub\n")
	return nil
}
