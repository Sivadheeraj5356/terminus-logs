package main

import "fmt"

// Assignment is one employee placed to work in one country. Rate is the
// employee's pay rate in micro-units per hour; Country is an ISO 3166-1 alpha-2
// code stored uppercased.
type Assignment struct {
	EmployeeID   int64
	EmployeeName string
	Rate         int64
	Country      string
}

// AddAssignment records that the employee works in the given country. Returns
// the error "exists" when that exact employee/country pairing is already
// recorded.
//
// Stub: the real implementation is supplied by the solution.
func AddAssignment(empID int64, country string) error {
	_, _ = empID, country
	return fmt.Errorf("not_implemented")
}

// ListAssignments returns every recorded assignment joined to its employee.
//
// Stub: the real implementation is supplied by the solution.
func ListAssignments() ([]Assignment, error) {
	return nil, fmt.Errorf("not_implemented")
}
