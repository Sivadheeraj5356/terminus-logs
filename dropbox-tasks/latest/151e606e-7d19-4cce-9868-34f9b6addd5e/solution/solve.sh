#!/bin/bash
set -euo pipefail
cat > /app/main.go <<'GOEOF'
package main

import (
	"bufio"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"math"
	"os"
)

const OS = 2     // ray oversampling of the forward model
const ITERS = 90 // reconstruction iterations
const qmax = 4095.0
const rmax = 100.0
const ascale = 1000000.0

var sync = []byte{0x54, 0x43}
var genesis = []byte("CTSCAN-1")

type Case struct {
	ImageSize int
	NDet      int
	Angles    []float64
	Sinogram  [][]float64
}

type Result struct {
	Sinogram [][]float64 `json:"sinogram"`
	Image    [][]float64 `json:"image"`
}

type Output struct {
	Results []Result `json:"results"`
}

// ---------- container codec ----------
func sh(parts ...[]byte) []byte {
	h := sha256.New()
	for _, p := range parts {
		h.Write(p)
	}
	return h.Sum(nil)
}

func mu(state []byte) float64 {
	return float64(4 + int(sh(state, []byte{0x04})[0])%37)
}

func expand(q int, m float64) float64 {
	u := math.Expm1(float64(q)/qmax*math.Log1p(m)) / m
	return u * rmax
}

func fy(seed4 []byte, n int) []int {
	s := binary.BigEndian.Uint32(seed4)
	p := make([]int, n)
	for i := range p {
		p[i] = i
	}
	for i := n - 1; i > 0; i-- {
		s = s*1664525 + 1013904223
		j := int(s % uint32(i+1))
		p[i], p[j] = p[j], p[i]
	}
	return p
}

func keystream(state []byte, dom byte, n int) []byte {
	out := make([]byte, 0, n+32)
	var ctr uint32 = 0
	for len(out) < n {
		var c [4]byte
		binary.BigEndian.PutUint32(c[:], ctr)
		out = append(out, sh(state, []byte{dom}, c[:])...)
		ctr++
	}
	return out[:n]
}

func decRec(state, cipher []byte) []byte {
	n := len(cipher)
	ks2 := keystream(state, 0x05, n)
	sb2 := fy(sh(state, []byte{0x06})[:4], 256)
	iv2 := sh(state, []byte{0x07})[0]
	sboxed := make([]byte, n)
	prev := int(iv2)
	for j := 0; j < n; j++ {
		sboxed[j] = cipher[j] ^ ks2[j] ^ byte(sb2[prev])
		prev = int(cipher[j])
	}
	sbox := fy(sh(state, []byte{0x03})[:4], 256)
	inv := make([]int, 256)
	for k := 0; k < 256; k++ {
		inv[sbox[k]] = k
	}
	permuted := make([]byte, n)
	for j := 0; j < n; j++ {
		permuted[j] = byte(inv[sboxed[j]])
	}
	perm := fy(sh(state, []byte{0x01})[:4], n)
	masked := make([]byte, n)
	for j := 0; j < n; j++ {
		masked[j] = permuted[perm[j]]
	}
	ks := keystream(state, 0x00, n)
	out := make([]byte, n)
	for j := 0; j < n; j++ {
		out[j] = masked[j] ^ ks[j]
	}
	return out
}

func ruv(buf []byte, pos int) (int, int) {
	var shift uint
	res := 0
	for {
		b := buf[pos]
		pos++
		res |= int(b&0x7F) << shift
		if b&0x80 == 0 {
			return res, pos
		}
		shift += 7
	}
}

func parseCase(plain []byte, m float64) Case {
	pos := 0
	var isz, ndet, na int
	isz, pos = ruv(plain, pos)
	ndet, pos = ruv(plain, pos)
	na, pos = ruv(plain, pos)
	angs := make([]float64, na)
	for i := 0; i < na; i++ {
		var a int
		a, pos = ruv(plain, pos)
		angs[i] = float64(a) / ascale
	}
	sino := make([][]float64, na)
	for i := 0; i < na; i++ {
		row := make([]float64, ndet)
		for j := 0; j < ndet; j++ {
			q := int(binary.BigEndian.Uint16(plain[pos : pos+2]))
			pos += 2
			row[j] = expand(q, m)
		}
		sino[i] = row
	}
	return Case{ImageSize: isz, NDet: ndet, Angles: angs, Sinogram: sino}
}

func decodeBatch(blob []byte) []Case {
	pos := 2
	nc := int(binary.BigEndian.Uint16(blob[pos : pos+2]))
	pos += 2
	seed := blob[pos : pos+4]
	pos += 4
	state := sh(sync, seed, genesis)
	cases := make([]Case, 0, nc)
	for i := 0; i < nc; i++ {
		m := mu(state)
		var ln int
		ln, pos = ruv(blob, pos)
		cipher := blob[pos : pos+ln]
		pos += ln
		plain := decRec(state, cipher)
		cases = append(cases, parseCase(plain, m))
		state = sh(state, plain)
	}
	return cases
}

// ---------- forward + reconstruction ----------
func forward(img [][]float64, ct, st []float64, N, M int) [][]float64 {
	c0 := float64(N-1) / 2.0
	dc := float64(M-1) / 2.0
	nos := N * OS
	sino := make([][]float64, len(ct))
	for ai := range ct {
		row := make([]float64, M)
		a := ct[ai]
		b := st[ai]
		for ti := 0; ti < M; ti++ {
			s := float64(ti) - dc
			var acc float64
			for k := 0; k < nos; k++ {
				u := (float64(k) - float64(nos-1)/2.0) / float64(OS)
				xs := s*a - u*b + c0
				ys := c0 - (s*b + u*a)
				x0 := int(math.Floor(xs))
				y0 := int(math.Floor(ys))
				fx := xs - float64(x0)
				fy := ys - float64(y0)
				for dy := 0; dy < 2; dy++ {
					wy := 1 - fy
					if dy == 1 {
						wy = fy
					}
					yi := y0 + dy
					if yi < 0 || yi >= N {
						continue
					}
					for dx := 0; dx < 2; dx++ {
						wx := 1 - fx
						if dx == 1 {
							wx = fx
						}
						xi := x0 + dx
						if xi < 0 || xi >= N {
							continue
						}
						acc += img[yi][xi] * wx * wy
					}
				}
			}
			row[ti] = acc / float64(OS)
		}
		sino[ai] = row
	}
	return sino
}

func backproject(sino [][]float64, ct, st []float64, N, M int) [][]float64 {
	c0 := float64(N-1) / 2.0
	dc := float64(M-1) / 2.0
	out := make([][]float64, N)
	for r := 0; r < N; r++ {
		out[r] = make([]float64, N)
	}
	for ai := range ct {
		a := ct[ai]
		b := st[ai]
		proj := sino[ai]
		for r := 0; r < N; r++ {
			y := c0 - float64(r)
			for col := 0; col < N; col++ {
				x := float64(col) - c0
				s := x*a + y*b + dc
				t0 := int(math.Floor(s))
				ft := s - float64(t0)
				var v float64
				if t0 >= 0 && t0 < M {
					v += proj[t0] * (1 - ft)
				}
				if t0+1 >= 0 && t0+1 < M {
					v += proj[t0+1] * ft
				}
				out[r][col] += v
			}
		}
	}
	return out
}

func reconstruct(c Case) [][]float64 {
	N := c.ImageSize
	M := c.NDet
	ct := make([]float64, len(c.Angles))
	st := make([]float64, len(c.Angles))
	for i, th := range c.Angles {
		ct[i] = math.Cos(th)
		st[i] = math.Sin(th)
	}
	ones := make([][]float64, N)
	for r := 0; r < N; r++ {
		ones[r] = make([]float64, N)
		for col := 0; col < N; col++ {
			ones[r][col] = 1.0
		}
	}
	R := forward(ones, ct, st, N, M)
	for ai := range R {
		for ti := range R[ai] {
			if R[ai][ti] > 1e-8 {
				R[ai][ti] = 1.0 / R[ai][ti]
			} else {
				R[ai][ti] = 0.0
			}
		}
	}
	onesSino := make([][]float64, len(c.Angles))
	for ai := range onesSino {
		onesSino[ai] = make([]float64, M)
		for ti := 0; ti < M; ti++ {
			onesSino[ai][ti] = 1.0
		}
	}
	C := backproject(onesSino, ct, st, N, M)
	for r := 0; r < N; r++ {
		for col := 0; col < N; col++ {
			if C[r][col] > 1e-8 {
				C[r][col] = 1.0 / C[r][col]
			} else {
				C[r][col] = 0.0
			}
		}
	}
	x := make([][]float64, N)
	for r := 0; r < N; r++ {
		x[r] = make([]float64, N)
	}
	for it := 0; it < ITERS; it++ {
		Ax := forward(x, ct, st, N, M)
		resid := make([][]float64, len(c.Angles))
		for ai := range Ax {
			resid[ai] = make([]float64, M)
			for ti := 0; ti < M; ti++ {
				resid[ai][ti] = R[ai][ti] * (c.Sinogram[ai][ti] - Ax[ai][ti])
			}
		}
		bp := backproject(resid, ct, st, N, M)
		for r := 0; r < N; r++ {
			for col := 0; col < N; col++ {
				v := x[r][col] + C[r][col]*bp[r][col]
				if v < 0 {
					v = 0
				}
				x[r][col] = v
			}
		}
	}
	return x
}

func main() {
	dec := json.NewDecoder(bufio.NewReader(os.Stdin))
	var in struct {
		Blob string `json:"blob"`
	}
	if err := dec.Decode(&in); err != nil {
		os.Exit(1)
	}
	raw, err := base64.StdEncoding.DecodeString(in.Blob)
	if err != nil {
		os.Exit(1)
	}
	cases := decodeBatch(raw)
	out := Output{Results: []Result{}}
	for _, c := range cases {
		img := reconstruct(c)
		out.Results = append(out.Results, Result{Sinogram: c.Sinogram, Image: img})
	}
	json.NewEncoder(os.Stdout).Encode(out)
}
GOEOF
cd /app && go build -o /app/ctrecon .
