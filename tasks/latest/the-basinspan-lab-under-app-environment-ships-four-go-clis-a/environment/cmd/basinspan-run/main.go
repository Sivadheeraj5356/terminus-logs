package main

import (
    "os"

    "bs7/internal/driver"
)

func main() {
    reset := false
    for _, a := range os.Args[1:] {
        if a == "--reset" {
            reset = true
        }
    }
    if err := driver.Execute(reset); err != nil {
        os.Exit(1)
    }
}
