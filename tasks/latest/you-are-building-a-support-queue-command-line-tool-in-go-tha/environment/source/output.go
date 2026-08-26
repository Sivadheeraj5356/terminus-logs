package main

import "fmt"

// printOK prints a success message to stdout.
func printOK(msg string) {
	fmt.Println(msg)
}

// printKeyVal prints a key=value line to stdout.
func printKeyVal(key string, value interface{}) {
	fmt.Printf("%s=%v\n", key, value)
}
