package engine

import "ucg.local/workspace/r2v"

func BindPack(dst, src *r2v.PackState, stamp uint32) uint32 {
	return r2v.Bind(dst, src, stamp)
}
