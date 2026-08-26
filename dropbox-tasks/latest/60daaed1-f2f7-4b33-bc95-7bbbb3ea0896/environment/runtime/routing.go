package main

import "net/http"

type Router struct {
	authz    *Authorizer
	guard    *Guard
	handlers *Handlers
}

func NewRouter(a *Authorizer, g *Guard, h *Handlers) *Router {
	return &Router{authz: a, guard: g, handlers: h}
}

func (r *Router) ServeHTTP(w http.ResponseWriter, req *http.Request) {
	canonicalPath := canonicalDispatchPath(req.URL.Path)
	if !isProtectedCanonicalPath(canonicalPath) {
		r.dispatchCanonical(w, req, canonicalPath, tokenRecord{})
		return
	}

	if rec, ok := r.authz.Check(req.Header.Get("Authorization")); ok {
		r.guard.RecordGrant(req.URL.Path, canonicalPath, rec)
		r.dispatchCanonical(w, req, canonicalPath, rec)
		return
	}

	if replayed, ok := r.guard.CanReuseGrant(req.URL.Path, canonicalPath); ok {
		r.dispatchCanonical(w, req, canonicalPath, replayed)
		return
	}

	writeUnauthorized(w)
}

func (r *Router) dispatchCanonical(w http.ResponseWriter, req *http.Request, canonicalPath string, who tokenRecord) {
	switch canonicalPath {
	case "/v1/public/ping":
		if req.Method != http.MethodGet {
			writeMethodNotAllowed(w)
			return
		}
		r.handlers.PublicPing(w, req)
	case "/v1/public/docs":
		if req.Method != http.MethodGet {
			writeMethodNotAllowed(w)
			return
		}
		r.handlers.PublicDocs(w, req)
	case "/v1/public/state":
		if req.Method != http.MethodGet {
			writeMethodNotAllowed(w)
			return
		}
		r.handlers.PublicState(w, req)
	case "/v1/admin/profile":
		if req.Method != http.MethodGet {
			writeMethodNotAllowed(w)
			return
		}
		r.handlers.AdminProfile(w, req, who)
	case "/v1/admin/audit":
		if req.Method != http.MethodGet {
			writeMethodNotAllowed(w)
			return
		}
		r.handlers.AdminAudit(w, req, who)
	default:
		writeNotFound(w)
	}
}
