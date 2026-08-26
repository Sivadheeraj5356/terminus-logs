#include "emit_d.h"

#include "ac_cfg.h"
#include "ac_sha.h"
#include "stage_mesh.h"

#include <fftw3.h>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <vector>

int emit_d(const char *profile, const ac_pressure_trace *trace, ac_formant_report *rep) {
    ac_lab_cfg cfg;
    ac_load_lab_cfg("/app/environment/config/lab.toml", &cfg);
    strncpy(rep->profile, profile, AC_MAX_PROFILE - 1);
    rep->profile[AC_MAX_PROFILE - 1] = '\0';
    rep->sample_rate_hz = cfg.sample_rate_hz;
    if (stage_mesh_read_digest(profile, rep->cavity_speed_digest, 65) != 0) {
        rep->cavity_speed_digest[0] = '\0';
        return -1;
    }

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
    std::vector<double> mag(nbins, 0.0);
    for (int k = 0; k < nbins; ++k) {
        mag[k] = std::hypot(out[k][0], out[k][1]);
    }

    struct peak {
        int bin;
        double hz;
        double db;
    };
    std::vector<peak> peaks;
    const double df = static_cast<double>(cfg.sample_rate_hz) / n;
    for (int k = 1; k < nbins - 1; ++k) {
        const double hz = k * df;
        if (hz < cfg.formant_min_hz || hz > cfg.formant_max_hz) {
            continue;
        }
        if (mag[k] <= mag[k - 1] || mag[k] <= mag[k + 1]) {
            continue;
        }
        const double db = 20.0 * std::log10(mag[k] + 1e-30);
        if (db < cfg.peak_min_db) {
            continue;
        }
        peaks.push_back({k, hz, db});
    }
    std::sort(peaks.begin(), peaks.end(), [](const peak &a, const peak &b) { return a.db > b.db; });

    rep->formant_count = 0;
    rep->peak_prominence_db = peaks.empty() ? 0.0 : peaks[0].db;
    if (!std::isfinite(rep->peak_prominence_db)) {
        rep->peak_prominence_db = 0.0;
    }
    for (const auto &pk : peaks) {
        if (rep->formant_count >= AC_MAX_FORMANTS) {
            break;
        }
        bool far = true;
        for (int j = 0; j < rep->formant_count; ++j) {
            if (std::fabs(rep->formants_hz[j] - pk.hz) < cfg.peak_min_sep_hz) {
                far = false;
                break;
            }
        }
        if (!far) {
            continue;
        }
        rep->formants_hz[rep->formant_count++] = pk.hz;
    }

    char payload[65536];
    int off = 0;
    for (int i = 0; i < trace->sample_count && off < static_cast<int>(sizeof payload) - 32; ++i) {
        off += snprintf(payload + off, sizeof payload - off, "%.6f,", trace->samples[i]);
    }
    ac_sha256_hex(payload, rep->pressure_digest, 65);

    fftw_destroy_plan(plan);
    fftw_free(in);
    fftw_free(out);
    return rep->formant_count == AC_MAX_FORMANTS ? 0 : -1;
}
