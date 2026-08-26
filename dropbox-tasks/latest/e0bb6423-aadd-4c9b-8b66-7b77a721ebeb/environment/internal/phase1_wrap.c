#include "pamlink/phase.h"
#include "pamlink/tally.h"

int phase1_tally(const tape_event *ev, int n) {
    return c3_tally(ev, n);
}
