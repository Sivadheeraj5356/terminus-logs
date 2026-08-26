package main

import "fmt"

// LogHours records a block of hours worked by the employee at time ts.
//
// Stub: the real implementation is supplied by the solution.
func LogHours(emp *Employee, hours, ts int64) error {
	_, _, _ = emp, hours, ts
	return fmt.Errorf("not_implemented")
}

// GrossPay returns the total gross pay in integer micro-units for the employee:
// the sum over the employee's recorded hours of hours times the pay rate.
//
// Stub: the real implementation is supplied by the solution.
func GrossPay(emp *Employee) (int64, error) {
	_ = emp
	return 0, fmt.Errorf("not_implemented")
}
