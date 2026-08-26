package main

func auditArchive(root string) []string {
	_, _, _, errs := validateCurrent(root)
	return errs
}
