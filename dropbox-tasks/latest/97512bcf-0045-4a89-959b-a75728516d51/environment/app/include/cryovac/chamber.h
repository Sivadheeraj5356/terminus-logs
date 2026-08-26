#ifndef CRYOVAC_CHAMBER_H
#define CRYOVAC_CHAMBER_H

#include "cryovac/types.h"

void cv_chamber_init(CvChamber *ch, double n_n2, double n_he, double volume_m3,
                     const CvSpecies *n2, const CvSpecies *he, const CvCalTable *cal,
                     const CvSolverCfg *solver);
int cv_chamber_advance(CvChamber *ch, double t, double temp_k, CvStepOut *out);

#endif
