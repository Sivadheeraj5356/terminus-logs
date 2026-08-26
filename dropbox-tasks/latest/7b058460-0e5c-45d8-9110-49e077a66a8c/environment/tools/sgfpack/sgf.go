package main

import (
	"errors"
	"fmt"
	"os"
	"regexp"
	"strings"
)

var propRE = regexp.MustCompile(`([A-Za-z_]+)\[([^\]]*)\]`)

func parseSGF(path string) (Game, error) {
	rawBytes, err := os.ReadFile(path)
	if err != nil {
		return Game{}, err
	}
	raw := strings.TrimSpace(string(rawBytes))
	if !strings.HasPrefix(raw, "(") || !strings.HasSuffix(raw, ")") {
		return Game{}, fmt.Errorf("%s is not a single SGF tree", path)
	}
	body := strings.TrimSuffix(strings.TrimPrefix(raw, "("), ")")
	pieces := strings.Split(body, ";")
	nodes := []string{}
	for _, piece := range pieces {
		piece = strings.TrimSpace(piece)
		if piece != "" {
			nodes = append(nodes, piece)
		}
	}
	if len(nodes) == 0 {
		return Game{}, fmt.Errorf("%s has no SGF nodes", path)
	}
	props := map[string]string{}
	for _, m := range propRE.FindAllStringSubmatch(nodes[0], -1) {
		props[m[1]] = m[2]
	}
	return Game{Props: props, Moves: nil, Raw: raw + "\n", Path: path}, nil
}

func sgfEsc(s string) string {
	s = strings.ReplaceAll(s, `\`, `\\`)
	return strings.ReplaceAll(s, "]", `\]`)
}

func buildSGF(card Card, moves []Move) string {
	props := []string{
		"GM[1]", "FF[4]", "CA[UTF-8]", "AP[sgfpack:2]", "SZ[5]",
		"RU[TTB-PSK-5]", "KM[0]", "EV[Harbor House 5x5 Cup]",
		fmt.Sprintf("RO[%d]", card.Round),
		fmt.Sprintf("ID[%s]", sgfEsc(card.GameID)),
		fmt.Sprintf("PB[%s]", sgfEsc(card.Black)),
		fmt.Sprintf("PW[%s]", sgfEsc(card.White)),
		fmt.Sprintf("RE[%s]", sgfEsc(card.Result)),
	}
	var sb strings.Builder
	sb.WriteString("(;")
	sb.WriteString(strings.Join(props, ""))
	sb.WriteString(")\n")
	return sb.String()
}

func boardKey(b [boardSize][boardSize]byte) string {
	return ""
}

func neighbors(x, y int) [][2]int {
	return nil
}

func groupAndLibs(b [boardSize][boardSize]byte, x, y int) (map[[2]int]bool, map[[2]int]bool) {
	return map[[2]int]bool{}, map[[2]int]bool{}
}

func place(b [boardSize][boardSize]byte, color byte, coord string) ([boardSize][boardSize]byte, error) {
	if len(coord) != 2 {
		return b, fmt.Errorf("bad coordinate %q", coord)
	}
	x := int(coord[0] - 'a')
	y := int(coord[1] - 'a')
	if x < 0 || x >= boardSize || y < 0 || y >= boardSize {
		return b, fmt.Errorf("coordinate %q outside 5x5 board", coord)
	}
	if b[y][x] != 0 {
		return b, fmt.Errorf("coordinate %q is occupied", coord)
	}
	b[y][x] = color
	return b, nil
}

func replay(g Game) (ReplayResult, error) {
	if g.Props["SZ"] != "5" || g.Props["RU"] != "TTB-PSK-5" {
		return ReplayResult{}, errors.New("SGF must declare SZ[5] and RU[TTB-PSK-5]")
	}
	re := g.Props["RE"]
	bp, wp := 0, 0
	reason := "score"
	if strings.HasSuffix(re, "+F") {
		reason = "superko-forfeit"
	}
	if strings.HasPrefix(re, "B+") {
		bp = 1
	} else if strings.HasPrefix(re, "W+") {
		wp = 1
	}
	return ReplayResult{Result: re, Reason: reason, BlackPoints: bp, WhitePoints: wp}, nil
}
