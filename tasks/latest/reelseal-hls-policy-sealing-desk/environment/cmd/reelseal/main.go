package main

import (
	"fmt"
	"os"

	"reelseal/internal/mediain"
	"reelseal/internal/stampv"
	"reelseal/internal/apiclient"
	"reelseal/internal/packgate"
	"reelseal/internal/cryptout"
	"reelseal/internal/hlsdrv"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: reelseal <fetch|segment|policy-bind|seal-manifest|hook-check|release-tag|package|run-all>")
		os.Exit(2)
	}
	api := env("REELSEAL_API", "http://127.0.0.1:8742")
	var err error
	switch os.Args[1] {
	case "fetch":
		src := ""
		if len(os.Args) > 2 {
			src = os.Args[2]
		}
		err = mediain.Run(src, "/app/state/media-fetch.json")
	case "segment":
		err = hlsdrv.Run("/app/state/media-fetch.json", "/app/state/hls")
	case "policy-bind":
		err = apiclient.BindPolicy(api, "/app/state/media-fetch.json", "/app/state/policy-bind.json")
	case "seal-manifest":
		err = cryptout.Seal("/app/state/policy-bind.json", "/app/state/hls", "/app/output/encryption-manifest.json")
	case "hook-check":
		err = stampv.Check("/app/output/encryption-manifest.json", "/app/state/validation-stamp.json")
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
	case "release-tag":
		err = packgate.CreateSignedTag()
	case "package":
		err = packgate.Package(
			"/app/output/encryption-manifest.json",
			"/app/state/validation-stamp.json",
			"/app/state/policy-bind.json",
			"/app/state/release-attest.json",
			"/app/output/release-package.tar",
			api,
		)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(3)
		}
	case "run-all":
		err = runAll(api)
	default:
		fmt.Fprintln(os.Stderr, "unknown command")
		os.Exit(2)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func runAll(api string) error {
	if err := mediain.Run("", "/app/state/media-fetch.json"); err != nil {
		return err
	}
	if err := hlsdrv.Run("/app/state/media-fetch.json", "/app/state/hls"); err != nil {
		return err
	}
	if err := apiclient.BindPolicy(api, "/app/state/media-fetch.json", "/app/state/policy-bind.json"); err != nil {
		return err
	}
	if err := cryptout.Seal("/app/state/policy-bind.json", "/app/state/hls", "/app/output/encryption-manifest.json"); err != nil {
		return err
	}
	if err := stampv.Check("/app/output/encryption-manifest.json", "/app/state/validation-stamp.json"); err != nil {
		return err
	}
	if err := packgate.CreateSignedTag(); err != nil {
		return err
	}
	return packgate.Package(
		"/app/output/encryption-manifest.json",
		"/app/state/validation-stamp.json",
		"/app/state/policy-bind.json",
		"/app/state/release-attest.json",
		"/app/output/release-package.tar",
		api,
	)
}

func env(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}
