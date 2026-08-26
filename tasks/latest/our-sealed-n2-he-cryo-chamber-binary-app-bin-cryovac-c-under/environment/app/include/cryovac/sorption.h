#ifndef CRYOVAC_SORPTION_H
#define CRYOVAC_SORPTION_H

#include "cryovac/types.h"

/* Competitive Langmuir: update ads/gas inventories in place. Returns 0 on success. */
int cv_sorption_equilibrate(CvChamber *ch, double temp_k);

#endif
