package main

import (
	"fmt"
	"os"
	"os/signal"
	"syscall"
)

func main() {
	if len(os.Args) < 2 || os.Args[1] != "serve" {
		usage()
		os.Exit(2)
	}
	ch := make(chan os.Signal, 1)
	signal.Notify(ch, syscall.SIGINT, syscall.SIGTERM)
	fmt.Println("supervisord ready")
	<-ch
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage: supervisord serve")
}
