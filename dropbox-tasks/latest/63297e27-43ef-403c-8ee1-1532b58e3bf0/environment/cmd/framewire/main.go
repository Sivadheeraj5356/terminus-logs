package main

import (
	"fmt"
	"io"
	"os"

	"framewire/internal/proto"
	"framewire/internal/wireio"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	switch os.Args[1] {
	case "frame":
		if len(os.Args) != 3 {
			fmt.Fprintln(os.Stderr, "usage: framewire frame <spec>")
			os.Exit(2)
		}
		runFrame(os.Args[2])
	case "send":
		if len(os.Args) != 3 {
			fmt.Fprintln(os.Stderr, "usage: framewire send <spec>")
			os.Exit(2)
		}
		runSend(os.Args[2])
	case "version":
		fmt.Println("framewire 0.3.0")
	default:
		fmt.Fprintln(os.Stderr, "framewire: unknown command: "+os.Args[1])
		os.Exit(2)
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage: framewire <command> [args]")
	fmt.Fprintln(os.Stderr, "commands:")
	fmt.Fprintln(os.Stderr, "  frame <spec>   encode one frontend message and print its wire framing")
	fmt.Fprintln(os.Stderr, "  send <spec>    encode one message through the frontend send path")
	fmt.Fprintln(os.Stderr, "  version        print the build version")
}

func runFrame(path string) {
	spec, err := proto.LoadSpec(path)
	if err != nil {
		fmt.Fprintln(os.Stderr, "frame: "+err.Error())
		os.Exit(2)
	}
	msg, err := spec.Build()
	if err != nil {
		fmt.Fprintln(os.Stderr, "frame: "+err.Error())
		os.Exit(2)
	}
	out, err := msg.Encode(nil)
	if err != nil {
		fmt.Fprintln(os.Stderr, err.Error())
		os.Exit(1)
	}
	fmt.Printf("ok kind=%s declared=%d intended=%d\n", spec.Kind, declaredLen(out), proto.IntendedFrameLen(msg))
}

func runSend(path string) {
	spec, err := proto.LoadSpec(path)
	if err != nil {
		fmt.Fprintln(os.Stderr, "send: "+err.Error())
		os.Exit(2)
	}
	msg, err := spec.Build()
	if err != nil {
		fmt.Fprintln(os.Stderr, "send: "+err.Error())
		os.Exit(2)
	}
	fe := proto.NewFrontend(io.Discard)
	if err := fe.Send(msg); err != nil {
		fmt.Fprintln(os.Stderr, err.Error())
		os.Exit(1)
	}
	fmt.Printf("sent kind=%s\n", spec.Kind)
}

func declaredLen(out []byte) int {
	if len(out) < 5 {
		return -1
	}
	return int(int32(wireio.Uint32(out[1:5])))
}
