#include "emit_d.h"

#include "ac_cfg.h"
#include "ac_sha.h"

#include <fftw3.h>

#include <cmath>
#include <cstring>

int emit_d(const char *profile, const ac_pressure_trace *trace, ac_formant_report *rep) {
    ac_lab_cfg cfg;
    ac_load_lab_cfg("/app/environment/config/lab.toml", &cfg);
    strncpy(rep->profile, profile, AC_MAX_PROFILE - 1);
    rep->profile[AC_MAX_PROFILE - 1] = '\0';
    rep->sample_rate_hz = cfg.sample_rate_hz;

    const int n = trace->sample_count;
    if (n < 64) {
        return -1;
    }

    double *in = fftw_alloc_real(n);
    fftw_complex *out = fftw_alloc_complex(n / 2 + 1);
    fftw_plan plan = fftw_plan_dft_r2c_1d(n, in, out, FFTW_ESTIMATE);
    for (int i = 0; i < n; ++i) {
        in[i] = trace->samples[i];
    }
    fftw_execute(plan);

    const int nbins = n / 2 + 1;
    const double df = static_cast<double>(cfg.sample_rate_hz) / n;
    rep->formant_count = 0;
    rep->peak_prominence_db = 0.0;
    for (int k = 0; k < nbins && rep->formant_count < AC_MAX_FORMANTS; ++k) {
        const double hz = k * df;
        if (hz > cfg.formant_max_hz) {
            break;
        }
        const double mag = std::hypot(out[k][0], out[k][1]);
        if (mag < 1e-6) {
            continue;
        }
        rep->formants_hz[rep->formant_count++] = hz;
        if (rep->formant_count == 1) {
            rep->peak_prominence_db = 20.0 * std::log10(mag + 1e-30);
        }
    }

    char payload[65536];
    int off = 0;
    for (int i = 0; i < trace->sample_count && off < static_cast<int>(sizeof payload) - 32; ++i) {
        off += snprintf(payload + off, sizeof payload - off, "%.6f,", trace->samples[i]);
    }
    ac_sha256_hex(payload, rep->pressure_digest, 65);
    rep->cavity_speed_digest[0] = '\0';

    fftw_destroy_plan(plan);
    fftw_free(in);
    fftw_free(out);
    return 0;
}
