#include "cryovac/sorption.h"
#include "cryovac/eos.h"

static int lock_n2_path(CvChamber *ch, double temp_k) {
    double locked_n2 = ch->n_ads_n2;
    double n_he = ch->n_gas_he + ch->n_ads_he;
    ch->n_gas_he = n_he;
    ch->n_ads_he = 0.0;

    double V = cv_free_volume(ch);
    double P = cv_pressure_binary(ch->n_gas_n2, ch->n_gas_he, V, temp_k, &ch->n2, &ch->he);
    double ntot = ch->n_gas_n2 + ch->n_gas_he;
    if (ntot <= 0.0 || P <= 0.0) {
        ch->n_ads_n2 = locked_n2;
        return 0;
    }
    double p1 = (ch->n_gas_n2 / ntot) * P;
    double p2 = (ch->n_gas_he / ntot) * P;
    double f1 = cv_fugacity(p1, ch->n2.b, P, temp_k);
    double f2 = cv_fugacity(p2, ch->he.b, P, temp_k);
    double K2 = ch->sorption.K_he;
    double denom = 1.0 + ch->sorption.K_n2 * f1 + K2 * f2;
    double theta2 = (K2 * f2) / denom;
    double sites = ch->sorption.n_sites - ch->n2.film_site_beta * ch->n_cond_n2;
    if (sites < 0.0) {
        sites = 0.0;
    }
    double want2 = sites * theta2;
    if (want2 > ch->n_gas_he) {
        want2 = ch->n_gas_he;
    }
    ch->n_ads_he = want2;
    ch->n_gas_he -= want2;
    ch->n_ads_n2 = locked_n2;
    return 0;
}

int cv_sorption_equilibrate(CvChamber *ch, double temp_k) {
    if (ch->frozen) {
        return lock_n2_path(ch, temp_k);
    }

    double n1 = ch->n_gas_n2 + ch->n_ads_n2;
    double n2 = ch->n_gas_he + ch->n_ads_he;
    ch->n_gas_n2 = n1;
    ch->n_gas_he = n2;
    ch->n_ads_n2 = 0.0;
    ch->n_ads_he = 0.0;

    double V = cv_free_volume(ch);
    double P = cv_pressure_binary(ch->n_gas_n2, ch->n_gas_he, V, temp_k, &ch->n2, &ch->he);
    double ntot = ch->n_gas_n2 + ch->n_gas_he;
    if (ntot <= 0.0 || P <= 0.0) {
        return 0;
    }
    double p1 = (ch->n_gas_n2 / ntot) * P;
    double p2 = (ch->n_gas_he / ntot) * P;
    double f1 = cv_fugacity(p1, ch->n2.b, P, temp_k);
    double f2 = cv_fugacity(p2, ch->he.b, P, temp_k);
    double K1 = ch->sorption.K_n2;
    double K2 = ch->sorption.K_he;
    double denom = 1.0 + K1 * f1 + K2 * f2;
    double theta1 = (K1 * f1) / denom;
    double theta2 = (K2 * f2) / denom;
    double sites = ch->sorption.n_sites;
    if (sites < 0.0) {
        sites = 0.0;
    }
    double want1 = sites * theta1;
    double want2 = sites * theta2;
    if (want1 > ch->n_gas_n2) {
        want1 = ch->n_gas_n2;
    }
    if (want2 > ch->n_gas_he) {
        want2 = ch->n_gas_he;
    }
    ch->n_ads_n2 = want1;
    ch->n_ads_he = want2;
    ch->n_gas_n2 -= want1;
    ch->n_gas_he -= want2;
    return 0;
}
