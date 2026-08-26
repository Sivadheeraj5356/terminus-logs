package main

var protectedRoutes = map[string]struct{}{
	"/v1/admin/profile": {},
	"/v1/admin/audit":   {},
}

func isProtectedCanonicalPath(p string) bool {
	_, ok := protectedRoutes[p]
	return ok
}
