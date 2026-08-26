#include "cryovac/chamber.h"
#include "cryovac/calibrate.h"
#include "cryovac/condense.h"
#include "cryovac/eos.h"
#include "cryovac/sorption.h"

#include <math.h>
#include <string.h>

void cv_chamber_init(CvChamber *ch, double n_n2, double n_he, double volume_m3,
                     const CvSpecies *n2, const CvSpecies *he, const CvCalTable *cal,
                     const CvSolverCfg *solver) {
    memset(ch, 0, sizeof(*ch));
    ch->n2 = *n2;
    ch->he = *he;
    ch->cal = *cal;
    ch->volume_m3 = volume_m3;
    ch->n_gas_n2 = n_n2;
    ch->n_gas_he = n_he;
    ch->sticky_seq = -1;
    ch->prev_cal_seq = -1;
    if (solver) {
        ch->solver = *solver;
    } else {
        ch->solver.max_solver_iters = 1;
        ch->solver.ads_tol = 1.0e-4;
        ch->solver.cond_tol = 1.0e-4;
    }
}

static int thermal_leg(CvChamber *ch, double temp_k) {
    if (!ch->has_prev_temp) {
        return CV_LEG_DESCEND;
    }
    if (temp_k < ch->prev_temp_k) {
        return CV_LEG_DESCEND;
    }
    if (temp_k > ch->prev_temp_k) {
        return CV_LEG_ASCEND;
    }
    return CV_LEG_DESCEND;
}

static int pick_sorption(CvChamber *ch, double temp_k, int leg, int *seq_out) {
    if (ch->sticky_seq >= 0) {
        const CvCalRow *sticky = cv_find_seq(&ch->cal, ch->sticky_seq);
        if (sticky && cv_sticky_eligible(&ch->cal, sticky, temp_k, leg, ch->prev_cal_seq)) {
            ch->sorption.K_n2 = sticky->K_n2;
            ch->sorption.K_he = sticky->K_he;
            ch->sorption.n_sites = sticky->n_sites;
            *seq_out = sticky->seq;
            return 0;
        }
    }
    if (cv_resolve_sorption(&ch->cal, temp_k, leg, ch->prev_cal_seq, &ch->sorption, seq_out) != 0) {
        return -1;
    }
    ch->sticky_seq = *seq_out;
    return 0;
}

int cv_chamber_advance(CvChamber *ch, double t, double temp_k, CvStepOut *out) {
    int leg = thermal_leg(ch, temp_k);
    int seq = 0;
    if (pick_sorption(ch, temp_k, leg, &seq) != 0) {
        return -1;
    }
    ch->active_cal_seq = seq;

    int was_frozen = ch->frozen;
    double cond_before = ch->n_cond_n2;
    int iters = 0;
    int max_iters = ch->solver.max_solver_iters > 0 ? ch->solver.max_solver_iters : 1;
    for (int i = 0; i < max_iters; i++) {
        iters = i + 1;
        double ads_n2_0 = ch->n_ads_n2;
        double ads_he_0 = ch->n_ads_he;
        double cond_0 = ch->n_cond_n2;
        if (cv_condense_equilibrate(ch, temp_k) != 0) {
            return -1;
        }
        if (cv_sorption_equilibrate(ch, temp_k) != 0) {
            return -1;
        }
        double d_ads = fabs(ch->n_ads_n2 - ads_n2_0) + fabs(ch->n_ads_he - ads_he_0);
        double d_cond = fabs(ch->n_cond_n2 - cond_0);
        if (d_cond < ch->solver.cond_tol) {
            (void)d_ads;
            break;
        }
    }

    if (ch->n_cond_n2 > cond_before + 1e-15) {
        ch->condensation_events += 1;
    }
    if (!was_frozen && ch->frozen) {
        ch->freeze_events += 1;
    }

    double V = cv_free_volume(ch);
    double P = cv_pressure_binary(ch->n_gas_n2, ch->n_gas_he, V, temp_k, &ch->n2, &ch->he);
    double ntot = ch->n_gas_n2 + ch->n_gas_he;
    out->t = t;
    out->temp_k = temp_k;
    out->p_total = P;
    out->n_gas_n2 = ch->n_gas_n2;
    out->n_gas_he = ch->n_gas_he;
    out->n_ads_n2 = ch->n_ads_n2;
    out->n_ads_he = ch->n_ads_he;
    out->n_cond_n2 = ch->n_cond_n2;
    out->x_he = (ntot > 0.0) ? (ch->n_gas_he / ntot) : 0.0;
    out->frozen = ch->frozen;
    out->cal_seq = ch->active_cal_seq;
    out->solver_iters = iters;
    out->thermal_leg = leg;
    if (ch->frozen) {
        out->regime = "frozen-film";
    } else if (ch->n_cond_n2 > 1e-15) {
        out->regime = "two-phase";
    } else {
        out->regime = "gas";
    }

    ch->prev_temp_k = temp_k;
    ch->prev_leg = leg;
    ch->has_prev_temp = 1;
    ch->prev_cal_seq = ch->active_cal_seq;
    return 0;
}
