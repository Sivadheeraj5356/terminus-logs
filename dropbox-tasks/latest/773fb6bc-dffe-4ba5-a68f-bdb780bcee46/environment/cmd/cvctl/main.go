package main

import (
	"os"

	"github.com/lab/cvstack/internal/driver"
)

func main() {
	os.Exit(driver.Run(os.Args))
}
