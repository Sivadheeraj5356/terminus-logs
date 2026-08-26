package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
)

func main() {
	tokenFile := "/app/fixtures/tokens.json"
	if v := os.Getenv("TOKEN_FILE"); v != "" {
		tokenFile = v
	}
	stateDir := "/app/runtime/state"
	if v := os.Getenv("STATE_DIR"); v != "" {
		stateDir = v
	}

	authz, err := NewAuthorizer(tokenFile)
	if err != nil {
		log.Fatalf("failed to init authorizer: %v", err)
	}
	replay, err := NewReplayStore(stateDir)
	if err != nil {
		log.Fatalf("failed to init replay store: %v", err)
	}
	guard := NewGuard(replay)
	h := NewHandlers(replay)
	r := NewRouter(authz, guard, h)

	addr := ":8080"
	fmt.Printf("listening on %s\n", addr)
	if err := http.ListenAndServe(addr, r); err != nil {
		log.Fatalf("server exited: %v", err)
	}
}
