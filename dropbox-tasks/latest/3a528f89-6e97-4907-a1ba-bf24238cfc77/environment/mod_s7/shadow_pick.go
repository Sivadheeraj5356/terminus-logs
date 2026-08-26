package mod_s7

import (
	"fmt"
	"log"
)

func LogPickPlan(gen uint32, lane string, nk uint32) {
	log.Printf("shadow pick lane=%s nk=%d gen=%d plan=%s", lane, nk, gen, fmt.Sprintf("g%02x", gen&0xff))
}
