#ifndef CRYOVAC_CONDENSE_H
#define CRYOVAC_CONDENSE_H

#include "cryovac/types.h"

double cv_vapor_pressure(const CvSpecies *sp, double temp_k);
/* Bulk condensation / evaporation of condensable species with freeze hysteresis. */
int cv_condense_equilibrate(CvChamber *ch, double temp_k);

#endif
