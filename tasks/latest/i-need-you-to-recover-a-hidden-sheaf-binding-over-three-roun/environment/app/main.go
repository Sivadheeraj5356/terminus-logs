// Tally dialer: the ONLY interface the player has to the keeper. It is a thin client that forwards
// one command line to the keeper over the Unix domain endpoint and prints the reply. It holds no
// game logic and knows no stretches; the keeper (a separate root job) owns all of that.
// Usage:
//
//	tally read
//	tally name 1,4,7
//	tally bind 2-4,8-11
//	tally next
//	tally help
package main

import (
	"fmt"
	"io"
	"net"
	"os"
	"strings"
)

func endpointPath() string {
	if v := os.Getenv("RB_KEEPER_ENDPOINT"); v != "" {
		return v
	}
	return "/run/ryebank/ryebank.sock"
}

func main() {
	cmd := strings.TrimSpace(strings.Join(os.Args[1:], " "))
	if cmd == "" {
		fmt.Fprintln(os.Stderr, "usage: tally <command> [args]   (try: tally help)")
		os.Exit(2)
	}
	conn, err := net.Dial("unix", endpointPath())
	if err != nil {
		fmt.Fprintf(os.Stderr, "tally: cannot reach the keeper (%v)\n", err)
		os.Exit(1)
	}
	defer conn.Close()
	if _, err := conn.Write([]byte(cmd + "\n")); err != nil {
		fmt.Fprintf(os.Stderr, "tally: write failed (%v)\n", err)
		os.Exit(1)
	}
	if uc, ok := conn.(*net.UnixConn); ok {
		_ = uc.CloseWrite()
	}
	out, _ := io.ReadAll(conn)
	os.Stdout.Write(out)
}
