// Command labyrinth-oracle serves the playtest hint oracle described in
// /app/docs/oracle-contract.md.
package main

import (
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"

	"labyrinthoracle/internal/httpapi"
	"labyrinthoracle/internal/scratchcheck"
	"labyrinthoracle/internal/session"
)

func usage() {
	fmt.Fprintln(os.Stderr, "usage: labyrinth-oracle serve --addr host:port")
	fmt.Fprintln(os.Stderr, "       labyrinth-oracle check --session-dir DIR --mode digest|route|abort")
}

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(1)
	}
	switch os.Args[1] {
	case "serve":
		serveCmd(os.Args[2:])
	case "check":
		checkCmd(os.Args[2:])
	default:
		usage()
		os.Exit(1)
	}
}

func serveCmd(args []string) {
	fs := flag.NewFlagSet("serve", flag.ExitOnError)
	addr := fs.String("addr", "127.0.0.1:8080", "listen address")
	_ = fs.Parse(args)

	store := session.NewStore()
	handler := httpapi.NewRouter(store)

	fmt.Printf("labyrinth-oracle: listening on %s\n", *addr)
	if err := http.ListenAndServe(*addr, handler); err != nil {
		log.Fatalf("labyrinth-oracle: %v", err)
	}
}

func checkCmd(args []string) {
	fs := flag.NewFlagSet("check", flag.ExitOnError)
	dir := fs.String("session-dir", "", "session scratch directory under /app/hint-scratch")
	mode := fs.String("mode", "", "digest, route, or abort")
	_ = fs.Parse(args)
	if *dir == "" || *mode == "" {
		usage()
		os.Exit(2)
	}
	var err error
	switch *mode {
	case "digest":
		err = scratchcheck.CheckDigest(*dir)
	case "route":
		err = scratchcheck.CheckRoute(*dir)
	case "abort":
		err = scratchcheck.CheckAbort(*dir)
	default:
		usage()
		os.Exit(2)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println("ok")
}
