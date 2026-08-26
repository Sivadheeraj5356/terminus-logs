#include "cryovac/condense.h"
#include "cryovac/eos.h"

#include <math.h>

double cv_vapor_pressure(const CvSpecies *sp, double temp_k) {
    if (temp_k <= 0.0) {
        return 0.0;
    }
    return sp->P_vap_ref * exp(-sp->L_vap / cv_R() * (1.0 / temp_k - 1.0 / sp->T_vap_ref));
}

static double pressure_n2_partial(const CvChamber *ch, double temp_k) {
    double V = cv_free_volume(ch);
    double P = cv_pressure_binary(ch->n_gas_n2, ch->n_gas_he, V, temp_k, &ch->n2, &ch->he);
    double ntot = ch->n_gas_n2 + ch->n_gas_he;
    if (ntot <= 0.0) {
        return 0.0;
    }
    return (ch->n_gas_n2 / ntot) * P;
}

static double find_n2_for_partial(CvChamber *ch, double temp_k, double target_p) {
    double lo = 1e-12;
    double hi = ch->n_gas_n2;
    if (pressure_n2_partial(ch, temp_k) <= target_p) {
        return ch->n_gas_n2;
    }
    double saved = ch->n_gas_n2;
    for (int i = 0; i < 64; i++) {
        double mid = 0.5 * (lo + hi);
        ch->n_gas_n2 = mid;
        if (pressure_n2_partial(ch, temp_k) > target_p) {
            hi = mid;
        } else {
            lo = mid;
        }
    }
    ch->n_gas_n2 = saved;
    return lo;
}

int cv_condense_equilibrate(CvChamber *ch, double temp_k) {
    if (ch->n_cond_n2 > 0.0 && temp_k <= ch->n2.T_freeze) {
        ch->frozen = 1;
    }
    if (ch->frozen && temp_k >= ch->n2.T_freeze) {
        ch->frozen = 0;
    }

    if (temp_k >= ch->n2.T_cond) {
        if (!ch->frozen && ch->n_cond_n2 > 0.0) {
            ch->n_gas_n2 += ch->n_cond_n2;
            ch->n_cond_n2 = 0.0;
        }
        return 0;
    }

    double Pv = cv_vapor_pressure(&ch->n2, temp_k);
    double p_n2 = pressure_n2_partial(ch, temp_k);

    if (p_n2 > Pv) {
        double n_new = find_n2_for_partial(ch, temp_k, Pv);
        double dn = ch->n_gas_n2 - n_new;
        if (dn > 0.0) {
            ch->n_gas_n2 = n_new;
            ch->n_cond_n2 += dn;
            if (temp_k <= ch->n2.T_freeze) {
                ch->frozen = 1;
            }
        }
    } else if (!ch->frozen && ch->n_cond_n2 > 0.0 && p_n2 < Pv) {
        double need = ch->n_cond_n2;
        double lo = 0.0;
        double hi = need;
        double base_gas = ch->n_gas_n2;
        for (int i = 0; i < 64; i++) {
            double mid = 0.5 * (lo + hi);
            ch->n_gas_n2 = base_gas + mid;
            if (pressure_n2_partial(ch, temp_k) < Pv) {
                lo = mid;
            } else {
                hi = mid;
            }
        }
        ch->n_gas_n2 = base_gas + lo;
        ch->n_cond_n2 = need - lo;
    }
    return 0;
}
