package main

import "fmt"

// LookupEmployee returns the employee with the given name, or nil when unknown.
//
// Stub: the real lookup is supplied by the solution.
func LookupEmployee(name string) (*Employee, error) {
	_ = name
	return nil, fmt.Errorf("not_implemented")
}

// AddEmployee creates a new employee and returns its id. Returns the error
// "exists" when the name is already registered.
//
// Stub: the real implementation is supplied by the solution.
func AddEmployee(name string, rate int64) (int64, error) {
	_, _ = name, rate
	return 0, fmt.Errorf("not_implemented")
}

// ListEmployees returns every employee sorted by name.
//
// Stub: the real implementation is supplied by the solution.
func ListEmployees() ([]Employee, error) {
	return nil, fmt.Errorf("not_implemented")
}
