package main

import (
	"os"

	"arctl.local/arctl/app"
)

func main() {
	os.Exit(app.Run(os.Args[1:]))
}
