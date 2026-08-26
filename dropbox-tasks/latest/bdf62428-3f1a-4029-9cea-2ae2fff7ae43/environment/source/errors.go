package main

import "fmt"

type notFoundError struct {
	kind string
	id   string
}

func (e *notFoundError) Error() string {
	return fmt.Sprintf("%s not found: %s", e.kind, e.id)
}

type alreadyExistsError struct {
	kind string
	id   string
}

func (e *alreadyExistsError) Error() string {
	return fmt.Sprintf("%s already exists: %s", e.kind, e.id)
}
