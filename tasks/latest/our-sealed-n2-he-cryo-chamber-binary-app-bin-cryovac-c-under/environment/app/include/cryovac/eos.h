#ifndef CRYOVAC_EOS_H
#define CRYOVAC_EOS_H

#include "cryovac/types.h"

double cv_R(void);
double cv_mix_a(double x1, double a1, double x2, double a2);
double cv_mix_b(double x1, double b1, double x2, double b2);
double cv_free_volume(const CvChamber *ch);
double cv_pressure_binary(double n1, double n2, double V, double T,
                          const CvSpecies *s1, const CvSpecies *s2);
double cv_fugacity(double p_i, double b_i, double P, double T);

#endif
