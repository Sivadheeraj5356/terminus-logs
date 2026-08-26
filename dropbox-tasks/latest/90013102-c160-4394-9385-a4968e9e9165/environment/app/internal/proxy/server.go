package proxy

import (
	"net"
	"os"

	"sigproxy/internal/audit"
	"sigproxy/internal/config"
	"sigproxy/internal/spool"
	"sigproxy/internal/trace"
)

type Server struct {
	Handler *Handler
	Listen  string
	Ready   string
}

func NewServer(rt *config.Runtime, mode string) (*Server, error) {
	traceW := trace.NewWriter(rt.Config.TracePath, mode, rt.Catalog.CatalogDigest)
	auditW := audit.NewSnapshotWriter(rt.Config.AuditLog)
	spoolW, err := spool.NewWriter(rt.Config.SpoolDir, rt.Config.SpoolSealKeyHex)
	if err != nil {
		return nil, err
	}
	return &Server{
		Handler: &Handler{
			Runtime: rt,
			TraceW:  traceW,
			AuditW:  auditW,
			SpoolW:  spoolW,
			Mode:    mode,
		},
		Listen: rt.Config.ListenUnix,
		Ready:  rt.Config.ReadyFile,
	}, nil
}

func (s *Server) Serve() error {
	_ = os.Remove(s.Listen)
	ln, err := net.Listen("unix", s.Listen)
	if err != nil {
		return err
	}
	if s.Ready != "" {
		_ = os.WriteFile(s.Ready, []byte("ready\n"), 0644)
	}
	for {
		conn, err := ln.Accept()
		if err != nil {
			return err
		}
		go s.Handler.HandleConn(conn)
	}
}

func (s *Server) FlushTrace() error {
	return s.Handler.TraceW.Flush()
}
